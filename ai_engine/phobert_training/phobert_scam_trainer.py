#!/usr/bin/env python3
"""
PhoBERT Scam Detection Trainer
Training PhoBERT model for Vietnamese child scam detection

Tuân thủ Privacy-by-Design:
- 100% synthetic data training
- No personal data processing
- Ethical AI compliance
"""

import os
import sys
import json
import logging
import torch
import numpy as np
import pandas as pd
from datetime import datetime
from typing import Dict, List, Tuple
from dataclasses import dataclass
from pathlib import Path

# ML libraries
from transformers import (
    AutoTokenizer, 
    AutoModelForSequenceClassification,
    TrainingArguments,
    Trainer,
    EarlyStoppingCallback
)
from sklearn.metrics import accuracy_score, precision_recall_fscore_support, classification_report
from sklearn.model_selection import train_test_split
import datasets
from datasets import Dataset, DatasetDict

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('logs/phobert_training.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

@dataclass
class TrainingConfig:
    """Cấu hình training PhoBERT"""
    model_name: str = "vinai/phobert-base"
    max_length: int = 256
    batch_size: int = 16
    learning_rate: float = 2e-5
    num_epochs: int = 3
    warmup_steps: int = 100
    weight_decay: float = 0.01
    save_steps: int = 200
    eval_steps: int = 200
    logging_steps: int = 50
    output_dir: str = "models/phobert_scam_detector"
    data_dir: str = "data/synthetic"
    
    # Early stopping
    early_stopping_patience: int = 3
    early_stopping_threshold: float = 0.001
    
    # GPU settings
    use_cuda: bool = torch.cuda.is_available()
    device: str = "cuda" if torch.cuda.is_available() else "cpu"

class PhoBERTScamTrainer:
    """Trainer cho PhoBERT scam detection"""
    
    def __init__(self, config: TrainingConfig):
        self.config = config
        self.tokenizer = None
        self.model = None
        self.trainer = None
        
        # Create output directory
        Path(config.output_dir).mkdir(parents=True, exist_ok=True)
        Path("logs").mkdir(exist_ok=True)
        
        logger.info(f"🚀 Initializing PhoBERT Scam Trainer")
        logger.info(f"📱 Device: {config.device}")
        logger.info(f"📊 Batch size: {config.batch_size}")
        logger.info(f"🔄 Epochs: {config.num_epochs}")
    
    def load_data(self) -> Tuple[Dataset, Dataset]:
        """Load và prepare training data"""
        logger.info("📥 Loading training data...")
        
        # Load training and validation datasets
        train_path = f"{self.config.data_dir}/phobert_train.json"
        val_path = f"{self.config.data_dir}/phobert_val.json"
        
        try:
            with open(train_path, 'r', encoding='utf-8') as f:
                train_data = json.load(f)
            
            with open(val_path, 'r', encoding='utf-8') as f:
                val_data = json.load(f)
            
            logger.info(f"✅ Loaded {len(train_data)} training samples")
            logger.info(f"✅ Loaded {len(val_data)} validation samples")
            
            # Convert to HuggingFace Dataset format
            train_dataset = Dataset.from_list(train_data)
            val_dataset = Dataset.from_list(val_data)
            
            # Log data statistics
            train_scam = sum(1 for item in train_data if item['label'] == 1)
            train_legit = sum(1 for item in train_data if item['label'] == 0)
            val_scam = sum(1 for item in val_data if item['label'] == 1)
            val_legit = sum(1 for item in val_data if item['label'] == 0)
            
            logger.info(f"📊 Training - Scam: {train_scam}, Legitimate: {train_legit}")
            logger.info(f"📊 Validation - Scam: {val_scam}, Legitimate: {val_legit}")
            
            return train_dataset, val_dataset
            
        except Exception as e:
            logger.error(f"❌ Failed to load data: {e}")
            raise
    
    def initialize_model_and_tokenizer(self):
        """Initialize PhoBERT model and tokenizer"""
        logger.info("🤖 Initializing PhoBERT model and tokenizer...")
        
        try:
            # Load tokenizer
            self.tokenizer = AutoTokenizer.from_pretrained(self.config.model_name)
            
            # Load model for sequence classification
            self.model = AutoModelForSequenceClassification.from_pretrained(
                self.config.model_name,
                num_labels=2,  # Binary classification: scam vs legitimate
                problem_type="single_label_classification"
            )
            
            # Move model to device
            self.model.to(self.config.device)
            
            logger.info(f"✅ Model loaded: {self.config.model_name}")
            logger.info(f"📱 Model device: {self.config.device}")
            logger.info(f"📊 Model parameters: {self.model.num_parameters():,}")
            
        except Exception as e:
            logger.error(f"❌ Failed to initialize model: {e}")
            raise
    
    def tokenize_dataset(self, dataset: Dataset) -> Dataset:
        """Tokenize dataset for PhoBERT"""
        logger.info("🔤 Tokenizing dataset...")
        
        def tokenize_function(examples):
            return self.tokenizer(
                examples["text"],
                padding="max_length",
                truncation=True,
                max_length=self.config.max_length,
                return_tensors="pt"
            )
        
        # Apply tokenization
        tokenized_dataset = dataset.map(
            tokenize_function,
            batched=True,
            remove_columns=["text", "scenario", "severity", "age_group", "realism_score", "risk_indicators", "metadata"]
        )
        
        # Set format for PyTorch
        tokenized_dataset.set_format("torch")
        
        logger.info(f"✅ Tokenization completed")
        return tokenized_dataset
    
    def compute_metrics(self, eval_pred):
        """Compute evaluation metrics"""
        logger.info("📊 Computing evaluation metrics...")
        
        predictions, labels = eval_pred
        predictions = np.argmax(predictions, axis=1)
        
        # Calculate metrics
        accuracy = accuracy_score(labels, predictions)
        precision, recall, f1, _ = precision_recall_fscore_support(
            labels, predictions, average='weighted'
        )
        
        # Calculate per-class metrics
        precision_per_class, recall_per_class, f1_per_class, _ = precision_recall_fscore_support(
            labels, predictions, average=None
        )
        
        metrics = {
            'accuracy': accuracy,
            'precision': precision,
            'recall': recall,
            'f1': f1,
            'precision_scam': precision_per_class[1],
            'recall_scam': recall_per_class[1],
            'f1_scam': f1_per_class[1],
            'precision_legitimate': precision_per_class[0],
            'recall_legitimate': recall_per_class[0],
            'f1_legitimate': f1_per_class[0]
        }
        
        return metrics
    
    def setup_trainer(self, train_dataset: Dataset, val_dataset: Dataset):
        """Setup HuggingFace Trainer"""
        logger.info("⚙️ Setting up trainer...")
        
        # Training arguments
        training_args = TrainingArguments(
            output_dir=self.config.output_dir,
            num_train_epochs=self.config.num_epochs,
            per_device_train_batch_size=self.config.batch_size,
            per_device_eval_batch_size=self.config.batch_size,
            learning_rate=self.config.learning_rate,
            weight_decay=self.config.weight_decay,
            warmup_steps=self.config.warmup_steps,
            logging_dir=f"{self.config.output_dir}/logs",
            logging_steps=self.config.logging_steps,
            save_steps=self.config.save_steps,
            eval_steps=self.config.eval_steps,
            evaluation_strategy="steps",
            save_strategy="steps",
            load_best_model_at_end=True,
            metric_for_best_model="f1",
            greater_is_better=True,
            report_to="none",  # Disable wandb/tensorboard for now
            fp16=self.config.use_cuda,  # Use mixed precision on GPU
            dataloader_num_workers=2,
        )
        
        # Initialize trainer
        self.trainer = Trainer(
            model=self.model,
            args=training_args,
            train_dataset=train_dataset,
            eval_dataset=val_dataset,
            compute_metrics=self.compute_metrics,
            callbacks=[EarlyStoppingCallback(early_stopping_patience=self.config.early_stopping_patience)]
        )
        
        logger.info("✅ Trainer setup completed")
    
    def train_model(self):
        """Train the PhoBERT model"""
        logger.info("🚀 Starting PhoBERT training...")
        
        try:
            # Start training
            train_result = self.trainer.train()
            
            # Log training results
            logger.info(f"✅ Training completed")
            logger.info(f"📊 Training loss: {train_result.training_loss:.4f}")
            logger.info(f"⏱️ Training time: {train_result.metrics['train_runtime']:.2f} seconds")
            
            # Save final model
            self.trainer.save_model()
            self.tokenizer.save_pretrained(self.config.output_dir)
            
            logger.info(f"💾 Model saved to {self.config.output_dir}")
            
            return train_result
            
        except Exception as e:
            logger.error(f"❌ Training failed: {e}")
            raise
    
    def evaluate_model(self):
        """Evaluate the trained model"""
        logger.info("📊 Evaluating model performance...")
        
        try:
            # Run evaluation
            eval_results = self.trainer.evaluate()
            
            # Log results
            logger.info("📈 Evaluation Results:")
            for metric, value in eval_results.items():
                if isinstance(value, float):
                    logger.info(f"   {metric}: {value:.4f}")
            
            # Generate classification report
            predictions = self.trainer.predict(self.trainer.eval_dataset)
            y_pred = np.argmax(predictions.predictions, axis=1)
            y_true = predictions.label_ids
            
            # Detailed classification report
            report = classification_report(
                y_true, y_pred, 
                target_names=['Legitimate', 'Scam'],
                output_dict=True
            )
            
            # Save evaluation results
            eval_results_path = f"{self.config.output_dir}/evaluation_results.json"
            with open(eval_results_path, 'w', encoding='utf-8') as f:
                json.dump({
                    'eval_results': eval_results,
                    'classification_report': report,
                    'training_config': {
                        'model_name': self.config.model_name,
                        'max_length': self.config.max_length,
                        'batch_size': self.config.batch_size,
                        'learning_rate': self.config.learning_rate,
                        'num_epochs': self.config.num_epochs
                    },
                    'timestamp': datetime.now().isoformat()
                }, f, ensure_ascii=False, indent=2)
            
            logger.info(f"📋 Evaluation results saved to {eval_results_path}")
            
            return eval_results, report
            
        except Exception as e:
            logger.error(f"❌ Evaluation failed: {e}")
            raise
    
    def test_model_samples(self):
        """Test model with sample texts"""
        logger.info("🧪 Testing model with sample texts...")
        
        test_samples = [
            "ae minh ơi, admin roblox đang event free robux nè! click vào link này verify acc thôi",
            "hello bạn, mình muốn hỏi về game roblox",
            "check out game mới skibidi này nè, click vào đây nè: bit.ly/skibidi-game",
            "ae ơi, ai chơi minecraft chung không?",
            "giveaway 1000 USDT nè! cần connect ví MetaMask tại link này",
            "hello, mình mới bắt đầu chơi roblox"
        ]
        
        try:
            self.model.eval()
            
            for i, text in enumerate(test_samples):
                # Tokenize input
                inputs = self.tokenizer(
                    text,
                    padding=True,
                    truncation=True,
                    max_length=self.config.max_length,
                    return_tensors="pt"
                )
                
                # Move to device
                inputs = {k: v.to(self.config.device) for k, v in inputs.items()}
                
                # Get prediction
                with torch.no_grad():
                    outputs = self.model(**inputs)
                    logits = outputs.logits
                    probabilities = torch.softmax(logits, dim=-1)
                    predicted_class = torch.argmax(probabilities, dim=-1).item()
                    confidence = probabilities[0][predicted_class].item()
                
                # Interpret results
                label = "SCAM" if predicted_class == 1 else "LEGITIMATE"
                confidence_pct = confidence * 100
                
                logger.info(f"🧪 Test {i+1}:")
                logger.info(f"   Text: {text[:50]}...")
                logger.info(f"   Prediction: {label} ({confidence_pct:.1f}%)")
                logger.info(f"   Confidence: {probabilities[0][0].item():.3f} (Legit) | {probabilities[0][1].item():.3f} (Scam)")
            
        except Exception as e:
            logger.error(f"❌ Model testing failed: {e}")
    
    def save_training_summary(self, train_result, eval_results):
        """Save comprehensive training summary"""
        logger.info("📋 Saving training summary...")
        
        summary = {
            'training_info': {
                'model_name': self.config.model_name,
                'training_completed': datetime.now().isoformat(),
                'total_training_time': train_result.metrics['train_runtime'],
                'final_training_loss': train_result.training_loss,
                'epochs_trained': train_result.log_history[-1]['epoch'] if train_result.log_history else self.config.num_epochs
            },
            'performance_metrics': eval_results,
            'model_info': {
                'total_parameters': self.model.num_parameters(),
                'model_size_mb': sum(p.numel() * p.element_size() for p in self.model.parameters()) / (1024*1024),
                'max_sequence_length': self.config.max_length,
                'device_used': self.config.device
            },
            'dataset_info': {
                'training_samples': len(self.trainer.train_dataset),
                'validation_samples': len(self.trainer.eval_dataset),
                'batch_size': self.config.batch_size
            },
            'compliance_note': {
                'data_source': '100% synthetic - Privacy compliant',
                'ethical_status': 'Safe for deployment',
                'intended_use': 'Vietnamese child scam detection'
            }
        }
        
        summary_path = f"{self.config.output_dir}/training_summary.json"
        with open(summary_path, 'w', encoding='utf-8') as f:
            json.dump(summary, f, ensure_ascii=False, indent=2)
        
        logger.info(f"📋 Training summary saved to {summary_path}")

def main():
    """Main training function"""
    logger.info("🚀 Starting PhoBERT Scam Detection Training")
    logger.info("🎯 Purpose: Vietnamese child scam detection")
    logger.info("🔒 Privacy: 100% synthetic data - Ethical AI")
    
    # Initialize configuration
    config = TrainingConfig()
    
    try:
        # Initialize trainer
        trainer = PhoBERTScamTrainer(config)
        
        # Load data
        train_dataset, val_dataset = trainer.load_data()
        
        # Initialize model and tokenizer
        trainer.initialize_model_and_tokenizer()
        
        # Tokenize datasets
        train_tokenized = trainer.tokenize_dataset(train_dataset)
        val_tokenized = trainer.tokenize_dataset(val_dataset)
        
        # Setup trainer
        trainer.setup_trainer(train_tokenized, val_tokenized)
        
        # Train model
        train_result = trainer.train_model()
        
        # Evaluate model
        eval_results, classification_report = trainer.evaluate_model()
        
        # Test with samples
        trainer.test_model_samples()
        
        # Save summary
        trainer.save_training_summary(train_result, eval_results)
        
        logger.info("🎉 PhoBERT training completed successfully!")
        logger.info(f"📁 Model saved to: {config.output_dir}")
        logger.info(f"📊 Best F1 Score: {eval_results['eval_f1']:.4f}")
        logger.info(f"🎯 Best Accuracy: {eval_results['eval_accuracy']:.4f}")
        
    except Exception as e:
        logger.error(f"❌ Training failed: {e}")
        raise

if __name__ == "__main__":
    main()
