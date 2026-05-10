#!/usr/bin/env python3
"""
XGBoost Fusion Model for ViFake Analytics
Multi-modal decision fusion combining vision and NLP features

Tuân thủ Privacy-by-Design:
- Zero-trust RAM processing
- Feature fusion without data persistence
- Ethical AI decision making
"""

import numpy as np
import pandas as pd
import logging
import joblib
import json
from typing import Dict, List, Tuple, Optional, Union
from dataclasses import dataclass
from datetime import datetime
import xgboost as xgb
from sklearn.model_selection import train_test_split, cross_val_score
from sklearn.metrics import accuracy_score, precision_recall_fscore_support, classification_report, confusion_matrix
from sklearn.preprocessing import StandardScaler

try:
    import shap
    SHAP_AVAILABLE = True
except ImportError:
    SHAP_AVAILABLE = False

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

@dataclass
class FusionConfig:
    """Cấu hình cho Fusion Model"""
    model_path: str = "ai_engine/fusion_model/xgboost_fusion_model.joblib"
    scaler_path: str = "ai_engine/fusion_model/feature_scaler.joblib"
    feature_names_path: str = "ai_engine/fusion_model/feature_names.json"
    
    # Model hyperparameters
    n_estimators: int = 100
    max_depth: int = 6
    learning_rate: float = 0.1
    subsample: float = 0.8
    colsample_bytree: float = 0.8
    
    # Training parameters
    test_size: float = 0.2
    random_state: int = 42
    cv_folds: int = 5
    
    # Feature thresholds
    vision_confidence_threshold: float = 0.7
    nlp_confidence_threshold: float = 0.7
    fusion_threshold: float = 0.5

class XGBoostFusionModel:
    """XGBoost-based multi-modal fusion classifier"""
    
    # Classification labels
    LABELS = ["SAFE", "FAKE_TOXIC", "FAKE_SCAM", "FAKE_MISINFO"]
    LABEL_MAP = {label: i for i, label in enumerate(LABELS)}
    
    def __init__(self, config: FusionConfig):
        self.config = config
        self.model = None
        self.scaler = None
        self.feature_names = []
        self.is_trained = False
        
        logger.info("🤖 Initializing XGBoost Fusion Model")
        logger.info(f"📊 Labels: {self.LABELS}")
    
    def extract_features(self, vision_result: Dict, nlp_result: Dict, metadata: Dict = None) -> np.ndarray:
        """Extract and combine features from vision and NLP results"""
        try:
            features = []
            
            # Vision features
            vision_features = self._extract_vision_features(vision_result)
            features.extend(vision_features)
            
            # NLP features
            nlp_features = self._extract_nlp_features(nlp_result)
            features.extend(nlp_features)
            
            # Metadata features
            if metadata:
                meta_features = self._extract_metadata_features(metadata)
                features.extend(meta_features)
            
            # Convert to numpy array
            feature_array = np.array(features, dtype=np.float32)
            
            # Store feature names for explainability
            if not self.feature_names:
                self.feature_names = self._get_feature_names(vision_result, nlp_result, metadata)
            
            return feature_array
            
        except Exception as e:
            logger.error(f"❌ Feature extraction failed: {e}")
            # Return zero features as fallback
            return np.zeros(len(self.feature_names) if self.feature_names else 50)
    
    def _extract_vision_features(self, vision_result: Dict) -> List[float]:
        """Extract features from vision analysis results"""
        features = []
        
        # Risk scores
        features.append(vision_result.get('combined_risk_score', 0.0))
        features.append(vision_result.get('safety_score', 0.0))
        
        # Individual risk categories
        features.append(vision_result.get('violent_risk', 0.0))
        features.append(vision_result.get('scam_risk', 0.0))
        features.append(vision_result.get('sexual_risk', 0.0))
        features.append(vision_result.get('inappropriate_risk', 0.0))
        
        # Binary flags
        features.append(1.0 if vision_result.get('is_safe', False) else 0.0)
        features.append(1.0 if vision_result.get('requires_review', False) else 0.0)
        
        # Risk level encoding
        risk_level = vision_result.get('risk_level', 'LOW')
        risk_encoding = {'LOW': 0.0, 'MEDIUM': 0.5, 'HIGH': 1.0}
        features.append(risk_encoding.get(risk_level, 0.0))
        
        # Confidence metrics
        features.append(vision_result.get('vram_usage_gb', 0.0) / 4.0)  # Normalized VRAM usage
        
        return features
    
    def _extract_nlp_features(self, nlp_result: Dict) -> List[float]:
        """Extract features from NLP analysis results"""
        features = []
        
        # Classification probabilities
        probs = nlp_result.get('probabilities', {})
        for label in self.LABELS:
            features.append(probs.get(label, 0.0))
        
        # Confidence score
        features.append(nlp_result.get('confidence', 0.0))
        
        # Binary flags
        features.append(1.0 if nlp_result.get('is_safe', False) else 0.0)
        features.append(1.0 if nlp_result.get('requires_review', False) else 0.0)
        
        # Risk level encoding
        risk_level = nlp_result.get('risk_level', 'LOW')
        risk_encoding = {'LOW': 0.0, 'MEDIUM': 0.5, 'HIGH': 1.0}
        features.append(risk_encoding.get(risk_level, 0.0))
        
        # Text features
        text = nlp_result.get('text', '')
        features.append(float(len(text)) / 500.0)  # Normalized text length
        features.append(float(text.count('http')) / 10.0)  # URL count
        features.append(float(text.count('!')) / 20.0)  # Exclamation count
        
        return features
    
    def _extract_metadata_features(self, metadata: Dict) -> List[float]:
        """Extract features from metadata"""
        features = []
        
        # Age group encoding
        age_group = metadata.get('age_group', 'unknown')
        age_encoding = {
            '8-10': 0.0, '11-13': 0.5, '14-17': 1.0, 'unknown': 0.25
        }
        features.append(age_encoding.get(age_group, 0.25))
        
        # Scenario encoding (one-hot for common scenarios)
        scenarios = ['robux_phishing', 'gift_card_scam', 'malicious_link', 'account_theft', 'crypto_scam']
        scenario = metadata.get('scenario', 'unknown')
        for s in scenarios:
            features.append(1.0 if scenario == s else 0.0)
        
        # Realism score
        features.append(metadata.get('realism_score', 0.0))
        
        # Conversation features
        features.append(float(metadata.get('conversation_turns', 0)) / 10.0)  # Normalized
        
        # Teencode indicator
        features.append(1.0 if metadata.get('contains_teencode', False) else 0.0)
        
        return features
    
    def _get_feature_names(self, vision_result: Dict, nlp_result: Dict, metadata: Dict) -> List[str]:
        """Generate feature names for explainability"""
        names = []
        
        # Vision feature names
        names.extend([
            'vision_combined_risk', 'vision_safety_score',
            'vision_violent_risk', 'vision_scam_risk', 'vision_sexual_risk', 'vision_inappropriate_risk',
            'vision_is_safe', 'vision_requires_review', 'vision_risk_level_encoded',
            'vision_vram_usage_normalized'
        ])
        
        # NLP feature names
        for label in self.LABELS:
            names.append(f'nlp_prob_{label.lower()}')
        names.extend([
            'nlp_confidence', 'nlp_is_safe', 'nlp_requires_review', 'nlp_risk_level_encoded',
            'nlp_text_length_normalized', 'nlp_url_count_normalized', 'nlp_exclamation_count_normalized'
        ])
        
        # Metadata feature names
        names.extend(['metadata_age_group_encoded'])
        scenarios = ['robux_phishing', 'gift_card_scam', 'malicious_link', 'account_theft', 'crypto_scam']
        for scenario in scenarios:
            names.append(f'metadata_scenario_{scenario}')
        names.extend(['metadata_realism_score', 'metadata_conversation_turns_normalized', 'metadata_contains_teencode'])
        
        return names
    
    def train(self, training_data: List[Dict]) -> Dict:
        """Train the fusion model"""
        logger.info(f"🚀 Training XGBoost Fusion Model with {len(training_data)} samples")
        
        try:
            # Extract features and labels
            X, y = self._prepare_training_data(training_data)
            
            if len(X) == 0:
                raise ValueError("No valid training data")
            
            # Split data
            X_train, X_test, y_train, y_test = train_test_split(
                X, y, 
                test_size=self.config.test_size,
                random_state=self.config.random_state,
                stratify=y
            )
            
            # Scale features
            self.scaler = StandardScaler()
            X_train_scaled = self.scaler.fit_transform(X_train)
            X_test_scaled = self.scaler.transform(X_test)
            
            # Initialize XGBoost model
            self.model = xgb.XGBClassifier(
                n_estimators=self.config.n_estimators,
                max_depth=self.config.max_depth,
                learning_rate=self.config.learning_rate,
                subsample=self.config.subsample,
                colsample_bytree=self.config.colsample_bytree,
                random_state=self.config.random_state,
                eval_metric='mlogloss',
                use_label_encoder=False
            )
            
            # Train model
            logger.info("📊 Training XGBoost model...")
            self.model.fit(X_train_scaled, y_train)
            
            # Evaluate model
            train_score = self.model.score(X_train_scaled, y_train)
            test_score = self.model.score(X_test_scaled, y_test)
            
            # Cross-validation
            cv_scores = cross_val_score(
                self.model, X_train_scaled, y_train, 
                cv=self.config.cv_folds, 
                scoring='accuracy'
            )
            
            # Detailed evaluation
            y_pred = self.model.predict(X_test_scaled)
            classification_rep = classification_report(y_test, y_pred, target_names=self.LABELS, output_dict=True)
            confusion_mat = confusion_matrix(y_test, y_pred)
            
            # Feature importance
            feature_importance = self.model.feature_importances_
            importance_df = pd.DataFrame({
                'feature': self.feature_names,
                'importance': feature_importance
            }).sort_values('importance', ascending=False)
            
            # Training results
            training_results = {
                'training_info': {
                    'samples_trained': len(training_data),
                    'features_used': len(self.feature_names),
                    'training_accuracy': train_score,
                    'test_accuracy': test_score,
                    'cv_mean_accuracy': cv_scores.mean(),
                    'cv_std_accuracy': cv_scores.std(),
                    'training_completed': datetime.now().isoformat()
                },
                'model_performance': {
                    'classification_report': classification_rep,
                    'confusion_matrix': confusion_mat.tolist(),
                    'feature_importance': importance_df.head(10).to_dict('records')
                },
                'model_config': {
                    'n_estimators': self.config.n_estimators,
                    'max_depth': self.config.max_depth,
                    'learning_rate': self.config.learning_rate
                }
            }
            
            # Save model and components
            self._save_model()
            
            self.is_trained = True
            
            logger.info(f"✅ Training completed!")
            logger.info(f"📊 Test accuracy: {test_score:.3f}")
            logger.info(f"📊 CV accuracy: {cv_scores.mean():.3f} ± {cv_scores.std():.3f}")
            
            return training_results
            
        except Exception as e:
            logger.error(f"❌ Training failed: {e}")
            raise
    
    def _prepare_training_data(self, training_data: List[Dict]) -> Tuple[np.ndarray, np.ndarray]:
        """Prepare training data from list of samples"""
        X = []
        y = []
        
        for sample in training_data:
            try:
                # Extract features
                features = self.extract_features(
                    sample['vision_result'],
                    sample['nlp_result'],
                    sample.get('metadata', {})
                )
                
                # Get label
                label = sample['label']
                if isinstance(label, str):
                    label_idx = self.LABEL_MAP.get(label, 0)
                else:
                    label_idx = int(label)
                
                X.append(features)
                y.append(label_idx)
                
            except Exception as e:
                logger.warning(f"⚠️ Skipping sample due to error: {e}")
                continue
        
        return np.array(X), np.array(y)
    
    def predict(self, vision_result: Dict, nlp_result: Dict, metadata: Dict = None) -> Dict:
        """Make prediction using fusion model"""
        if not self.is_trained:
            logger.error("❌ Model not trained yet")
            return self._fallback_prediction(vision_result, nlp_result)
        
        try:
            # Extract features
            features = self.extract_features(vision_result, nlp_result, metadata)
            
            # Scale features
            features_scaled = self.scaler.transform([features])
            
            # Make prediction
            prediction_proba = self.model.predict_proba(features_scaled)[0]
            prediction_idx = self.model.predict(features_scaled)[0]
            
            # Get prediction label
            prediction_label = self.LABELS[prediction_idx]
            confidence = prediction_proba[prediction_idx]
            
            # Risk assessment
            risk_level = self._assess_fusion_risk(prediction_label, confidence)
            
            return {
                'prediction': prediction_label,
                'prediction_idx': int(prediction_idx),
                'confidence': float(confidence),
                'probabilities': {
                    self.LABELS[i]: float(prob) 
                    for i, prob in enumerate(prediction_proba)
                },
                'risk_level': risk_level,
                'is_safe': prediction_label == 'SAFE',
                'requires_review': prediction_label != 'SAFE' and confidence < 0.8,
                'fusion_method': 'xgboost',
                'feature_count': len(features),
                'model_version': 'v1.0'
            }
            
        except Exception as e:
            logger.error(f"❌ Prediction failed: {e}")
            return self._fallback_prediction(vision_result, nlp_result)
    
    def _fallback_prediction(self, vision_result: Dict, nlp_result: Dict) -> Dict:
        """Fallback prediction when model is not available"""
        # Simple rule-based fusion
        vision_safe = vision_result.get('is_safe', True)
        nlp_safe = nlp_result.get('is_safe', True)
        vision_risk = vision_result.get('combined_risk_score', 0.0)
        nlp_confidence = nlp_result.get('confidence', 0.5)
        
        if vision_safe and nlp_safe:
            prediction = 'SAFE'
            confidence = 0.8
        elif vision_risk > 0.7 or not nlp_safe:
            prediction = 'FAKE_SCAM'
            confidence = max(vision_risk, 1.0 - nlp_confidence)
        else:
            prediction = 'FAKE_TOXIC'
            confidence = 0.6
        
        return {
            'prediction': prediction,
            'confidence': confidence,
            'probabilities': {label: 0.25 for label in self.LABELS},
            'risk_level': 'HIGH' if prediction != 'SAFE' else 'LOW',
            'is_safe': prediction == 'SAFE',
            'requires_review': prediction != 'SAFE',
            'fusion_method': 'rule_based_fallback',
            'model_version': 'fallback'
        }
    
    def _assess_fusion_risk(self, prediction: str, confidence: float) -> str:
        """Assess risk level from fusion prediction"""
        if prediction == 'SAFE':
            return 'LOW'
        elif confidence >= 0.8:
            return 'HIGH'
        elif confidence >= 0.6:
            return 'MEDIUM'
        else:
            return 'LOW'
    
    def explain_prediction(self, vision_result: Dict, nlp_result: Dict, metadata: Dict = None) -> Dict:
        """Explain prediction using SHAP values"""
        if not self.is_trained:
            return {'error': 'Model not trained for explanation'}
        
        try:
            if not SHAP_AVAILABLE:
                return {'error': 'shap package not installed'}
            import shap
            
            # Extract features
            features = self.extract_features(vision_result, nlp_result, metadata)
            features_scaled = self.scaler.transform([features])
            
            # Create SHAP explainer
            explainer = shap.TreeExplainer(self.model)
            shap_values = explainer.shap_values(features_scaled)
            
            # For multi-class, get SHAP values for the predicted class
            if isinstance(shap_values, list):
                # Get prediction to determine which class to explain
                pred_idx = self.model.predict(features_scaled)[0]
                shap_vals = shap_values[pred_idx][0]  # Values for predicted class
            else:
                shap_vals = shap_values[0]
            
            # Create explanation
            feature_importance = list(zip(self.feature_names, shap_vals, features))
            feature_importance.sort(key=lambda x: abs(x[1]), reverse=True)
            
            return {
                'explanation_method': 'SHAP',
                'top_features': [
                    {
                        'feature': name,
                        'shap_value': float(value),
                        'feature_value': float(feat_val)
                    }
                    for name, value, feat_val in feature_importance[:10]
                ],
                'base_value': float(explainer.expected_value) if hasattr(explainer, 'expected_value') else 0.0,
                'prediction_explained': True
            }
            
        except Exception as e:
            logger.error(f"❌ Explanation failed: {e}")
            return {'error': f'Explanation failed: {str(e)}'}
    
    def _save_model(self):
        """Save model and components"""
        logger.info("💾 Saving fusion model...")
        
        try:
            # Create directory
            os.makedirs(os.path.dirname(self.config.model_path), exist_ok=True)
            
            # Save model
            joblib.dump(self.model, self.config.model_path)
            
            # Save scaler
            joblib.dump(self.scaler, self.config.scaler_path)
            
            # Save feature names
            with open(self.config.feature_names_path, 'w') as f:
                json.dump(self.feature_names, f, indent=2)
            
            logger.info(f"✅ Model saved to {self.config.model_path}")
            
        except Exception as e:
            logger.error(f"❌ Model saving failed: {e}")
            raise
    
    def load_model(self):
        """Load trained model"""
        logger.info("📂 Loading fusion model...")
        
        try:
            # Load model
            self.model = joblib.load(self.config.model_path)
            
            # Load scaler
            self.scaler = joblib.load(self.config.scaler_path)
            
            # Load feature names
            with open(self.config.feature_names_path, 'r') as f:
                self.feature_names = json.load(f)
            
            self.is_trained = True
            
            logger.info("✅ Model loaded successfully")
            
        except Exception as e:
            logger.error(f"❌ Model loading failed: {e}")
            raise
    
    def get_model_info(self) -> Dict:
        """Get model information"""
        if not self.is_trained:
            return {'status': 'not_trained'}
        
        return {
            'status': 'trained',
            'model_type': 'XGBoostClassifier',
            'feature_count': len(self.feature_names),
            'class_count': len(self.LABELS),
            'labels': self.LABELS,
            'feature_names': self.feature_names,
            'config': {
                'n_estimators': self.config.n_estimators,
                'max_depth': self.config.max_depth,
                'learning_rate': self.config.learning_rate
            }
        }

# Global fusion model instance
_fusion_model = None

def get_fusion_model() -> XGBoostFusionModel:
    """Get singleton fusion model instance"""
    global _fusion_model
    if _fusion_model is None:
        config = FusionConfig()
        _fusion_model = XGBoostFusionModel(config)
        
        # Try to load existing model
        try:
            _fusion_model.load_model()
        except:
            logger.info("🆕 No existing model found, starting fresh")
    
    return _fusion_model

if __name__ == "__main__":
    # Test fusion model
    logger.info("🧪 Testing XGBoost Fusion Model...")
    
    try:
        fusion = get_fusion_model()
        logger.info("✅ Fusion model initialized")
        
        # Test with dummy data
        dummy_vision = {
            'combined_risk_score': 0.3,
            'safety_score': 0.7,
            'violent_risk': 0.1,
            'scam_risk': 0.2,
            'sexual_risk': 0.0,
            'inappropriate_risk': 0.1,
            'is_safe': True,
            'requires_review': False,
            'risk_level': 'LOW',
            'vram_usage_gb': 1.2
        }
        
        dummy_nlp = {
            'probabilities': {'SAFE': 0.8, 'FAKE_TOXIC': 0.1, 'FAKE_SCAM': 0.05, 'FAKE_MISINFO': 0.05},
            'confidence': 0.8,
            'is_safe': True,
            'requires_review': False,
            'risk_level': 'LOW',
            'text': 'This is a safe message for children'
        }
        
        dummy_metadata = {
            'age_group': '11-13',
            'scenario': 'legitimate',
            'realism_score': 0.9,
            'conversation_turns': 2,
            'contains_teencode': False
        }
        
        # Test prediction
        result = fusion.predict(dummy_vision, dummy_nlp, dummy_metadata)
        logger.info(f"🎯 Test prediction: {result['prediction']} (confidence: {result['confidence']:.3f})")
        
        logger.info("✅ Fusion model test completed")
        
    except Exception as e:
        logger.error(f"❌ Fusion model test failed: {e}")
        raise
