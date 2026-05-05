# ai_engine/nlp_worker/translate_pipeline.py
import json
import os
from datasets import load_dataset
from transformers import pipeline

# Load the translator
print("Loading Helsinki-NLP translation model...")
translator = pipeline(
    "translation_en_to_vi",
    model="Helsinki-NLP/opus-mt-en-vi",
    device=-1,  # Set to -1 to run on CPU
)

def translate_anli_batch(examples: dict) -> dict:
    """
    Input: batch from ANLI dataset
    Output: same structure but text translated to Vietnamese
    """
    translated_premises = translator(
        examples["premise"],
        batch_size=16,
        truncation=True,
    )
    translated_hypotheses = translator(
        examples["hypothesis"],
        batch_size=16,
        truncation=True,
    )
    
    return {
        "premise_vi": [t["translation_text"] for t in translated_premises],
        "hypothesis_vi": [t["translation_text"] for t in translated_hypotheses],
        "label": examples["label"],  # 0=entail, 1=neutral, 2=contradict
    }

def main():
    print("Loading ANLI dataset...")
    # For a fast setup/demo, we can load a slice of the dataset
    # You can customize it to load everything
    anli_dataset = load_dataset("facebook/anli", split="train_r3")
    
    # Let's take the first 100 examples to make it quick for setup/demo purposes
    print("Slicing 100 examples for local translation test...")
    anli_subset = anli_dataset.select(range(min(100, len(anli_dataset))))

    print("Mapping translation over the subset...")
    anli_vi = anli_subset.map(translate_anli_batch, batched=True, batch_size=16)

    output_dir = "data/processed/anli_vi/"
    os.makedirs(output_dir, exist_ok=True)
    anli_vi.save_to_disk(output_dir)
    print(f"Saved {len(anli_vi)} translated examples to {output_dir}")

if __name__ == "__main__":
    main()
