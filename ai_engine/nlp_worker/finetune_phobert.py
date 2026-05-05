# ai_engine/nlp_worker/finetune_phobert.py
import os
import numpy as np
import mlflow
from datasets import load_dataset, load_from_disk, concatenate_datasets
from transformers import (
    AutoTokenizer, AutoModelForSequenceClassification,
    TrainingArguments, Trainer, DataCollatorWithPadding,
)
from sklearn.metrics import f1_score

MODEL_NAME = "vinai/phobert-base"

print("Loading PhoBERT tokenizer...")
tokenizer = AutoTokenizer.from_pretrained(MODEL_NAME)

def prepare_combined_dataset():
    """
    Combined:
    - ANLI Vietnamese (reasoning capability)
    - ViHSD (Vietnamese hate speech domain)
    
    Mapped into 3 distinct labels:
    0 = SAFE
    1 = TOXIC
    2 = MANIPULATIVE
    """
    print("Loading ViHSD dataset...")
    try:
        vihsd = load_dataset("phongphanmtb/vihsd")
        vihsd_train = vihsd["train"]
    except Exception:
        # Fallback dataset if ViHSD load fails
        from datasets import Dataset
        print("Fallback: Using a small dummy dataset for testing")
        vihsd_train = Dataset.from_dict({
            "free_text": ["nội dung này an toàn", "nội dung này độc hại", "tin giả lừa đảo"],
            "label_id": [0, 1, 2]
        })
    
    # ViHSD labels: 0=clean, 1=offensive, 2=hate
    vihsd_mapped = vihsd_train.map(lambda x: {
        "text": x.get("free_text") or x.get("text", ""),
        "label": 0 if x.get("label_id", 0) == 0 else 1,
    })
    
    anli_vi_path = "data/processed/anli_vi/"
    if os.path.exists(anli_vi_path):
        print(f"Loading local translated ANLI from {anli_vi_path}")
        anli_vi = load_from_disk(anli_vi_path)
    else:
        # Fallback if ANLI was not processed yet
        from datasets import Dataset
        print("Fallback: Using dummy ANLI translated data")
        anli_vi = Dataset.from_dict({
            "premise_vi": ["Trẻ em nên được bảo vệ", "Nội dung giáo dục"],
            "hypothesis_vi": ["Thế giới cần bảo vệ trẻ em", "Toán học cơ bản"],
            "label": [2, 0]
        })

    anli_mapped = anli_vi.map(lambda x: {
        "text": x.get("premise_vi", "") + " [SEP] " + x.get("hypothesis_vi", ""),
        "label": 2 if x.get("label", 0) == 2 else 0,
    }).filter(lambda x: x["label"] in [0, 2])

    print("Concatenating datasets...")
    return concatenate_datasets([vihsd_mapped, anli_mapped]).shuffle(seed=42)

def tokenize(examples):
    return tokenizer(
        examples["text"],
        truncation=True,
        max_length=256,
        padding=False,
    )

def compute_metrics(eval_pred):
    logits, labels = eval_pred
    preds = np.argmax(logits, axis=-1)
    return {
        "f1_macro": f1_score(labels, preds, average="macro"),
        "f1_weighted": f1_score(labels, preds, average="weighted"),
    }

def main():
    dataset = prepare_combined_dataset()
    tokenized = dataset.map(tokenize, batched=True, remove_columns=["text"])
    
    split = tokenized.train_test_split(test_size=0.1, seed=42)
    
    print("Loading PhoBERT model...")
    model = AutoModelForSequenceClassification.from_pretrained(
        MODEL_NAME,
        num_labels=3,
        ignore_mismatched_sizes=True,
    )

    # Freeze PhoBERT backbone - only train the classifier layers to save CPU/GPU resources
    print("Freezing backbone parameters...")
    for name, param in model.roberta.named_parameters():
        param.requires_grad = False

    training_args = TrainingArguments(
        output_dir="ai_engine/nlp_worker/phobert_finetuned/",
        num_train_epochs=1,  # Short training for quick setup/demo
        per_device_train_batch_size=4,
        per_device_eval_batch_size=4,
        learning_rate=2e-5,
        weight_decay=0.01,
        evaluation_strategy="epoch",
        save_strategy="epoch",
        load_best_model_at_end=True,
        metric_for_best_model="f1_macro",
        logging_dir="logs/phobert_training/",
        report_to="none",
    )

    print("Starting Training using Trainer API...")
    trainer = Trainer(
        model=model,
        args=training_args,
        train_dataset=split["train"],
        eval_dataset=split["test"],
        tokenizer=tokenizer,
        data_collator=DataCollatorWithPadding(tokenizer),
        compute_metrics=compute_metrics,
    )

    trainer.train()

    # Log metrics
    metrics = trainer.evaluate()
    print(f"Evaluation Metrics: {metrics}")
    
    output_model_dir = "ai_engine/nlp_worker/phobert_finetuned/best_model"
    os.makedirs(output_model_dir, exist_ok=True)
    model.save_pretrained(output_model_dir)
    tokenizer.save_pretrained(output_model_dir)
    print(f"Best model saved to {output_model_dir}")

if __name__ == "__main__":
    main()
