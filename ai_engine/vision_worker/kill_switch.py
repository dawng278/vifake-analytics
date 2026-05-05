#!/usr/bin/env python3
"""
Vision Worker Kill Switch - Emergency VRAM Management
Memory optimization and OOM prevention for RTX 2050 (4GB VRAM)

Tuân thủ Privacy-by-Design:
- Zero-trust RAM processing
- Emergency cleanup without data persistence
- GPU memory safety mechanisms
"""

import torch
import gc
import psutil
import logging
from typing import Dict, Optional
from dataclasses import dataclass
from datetime import datetime

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

@dataclass
class MemoryConfig:
    """Cấu hình quản lý memory"""
    max_vram_usage_gb: float = 3.2  # 80% of 4GB VRAM
    max_ram_usage_gb: float = 12.0  # Conservative RAM limit
    cleanup_threshold: float = 0.8   # Cleanup at 80% usage
    emergency_threshold: float = 0.95  # Emergency at 95%
    
    # Monitoring frequency
    monitor_interval_seconds: int = 30
    cleanup_cooldown_seconds: int = 5

class VisionKillSwitch:
    """Emergency memory management for vision worker"""
    
    def __init__(self, config: MemoryConfig):
        self.config = config
        self.last_cleanup_time = datetime.now()
        self.cleanup_count = 0
        self.emergency_count = 0
        
        logger.info("🛡️ Vision Kill Switch initialized")
        logger.info(f"📱 Max VRAM: {self.config.max_vram_usage_gb} GB")
        logger.info(f"💾 Max RAM: {self.config.max_ram_usage_gb} GB")
    
    def get_memory_status(self) -> Dict[str, float]:
        """Get current memory usage status"""
        status = {}
        
        # VRAM usage
        if torch.cuda.is_available():
            vram_allocated = torch.cuda.memory_allocated() / (1024**3)
            vram_reserved = torch.cuda.memory_reserved() / (1024**3)
            vram_total = torch.cuda.get_device_properties(0).total_memory / (1024**3)
            
            status.update({
                'vram_allocated_gb': vram_allocated,
                'vram_reserved_gb': vram_reserved,
                'vram_total_gb': vram_total,
                'vram_usage_ratio': vram_allocated / vram_total,
                'vram_reserved_ratio': vram_reserved / vram_total
            })
        else:
            status.update({
                'vram_allocated_gb': 0.0,
                'vram_reserved_gb': 0.0,
                'vram_total_gb': 0.0,
                'vram_usage_ratio': 0.0,
                'vram_reserved_ratio': 0.0
            })
        
        # RAM usage
        ram = psutil.virtual_memory()
        status.update({
            'ram_used_gb': ram.used / (1024**3),
            'ram_total_gb': ram.total / (1024**3),
            'ram_usage_ratio': ram.percent / 100.0
        })
        
        return status
    
    def check_memory_pressure(self) -> str:
        """Check current memory pressure level"""
        status = self.get_memory_status()
        
        vram_ratio = status['vram_usage_ratio']
        ram_ratio = status['ram_usage_ratio']
        
        max_ratio = max(vram_ratio, ram_ratio)
        
        if max_ratio >= self.config.emergency_threshold:
            return "EMERGENCY"
        elif max_ratio >= self.config.cleanup_threshold:
            return "HIGH"
        elif max_ratio >= 0.6:
            return "MEDIUM"
        else:
            return "LOW"
    
    def cleanup_vram(self, force: bool = False) -> bool:
        """Clean up VRAM with cooldown check"""
        now = datetime.now()
        cooldown_passed = (now - self.last_cleanup_time).total_seconds() > self.config.cleanup_cooldown_seconds
        
        if not force and not cooldown_passed:
            logger.debug("⏱️ Cleanup in cooldown, skipping")
            return False
        
        logger.info("🧹 Cleaning up VRAM...")
        
        try:
            # Clear CUDA cache
            if torch.cuda.is_available():
                initial_vram = torch.cuda.memory_allocated() / (1024**3)
                
                # Multiple cleanup strategies
                torch.cuda.empty_cache()
                torch.cuda.synchronize()
                
                # Force garbage collection
                gc.collect()
                
                # Additional cache clearing
                torch.cuda.empty_cache()
                
                final_vram = torch.cuda.memory_allocated() / (1024**3)
                freed_vram = initial_vram - final_vram
                
                self.cleanup_count += 1
                self.last_cleanup_time = now
                
                logger.info(f"✅ VRAM cleanup completed")
                logger.info(f"💾 Freed {freed_vram:.2f} GB VRAM")
                logger.info(f"📱 Current VRAM: {final_vram:.2f} GB")
                
                return True
                
        except Exception as e:
            logger.error(f"❌ VRAM cleanup failed: {e}")
            return False
    
    def emergency_cleanup(self) -> bool:
        """Emergency cleanup for critical memory situations"""
        logger.warning("🚨 EMERGENCY CLEANUP TRIGGERED!")
        
        try:
            # Record emergency
            self.emergency_count += 1
            
            # Get pre-cleanup status
            status_before = self.get_memory_status()
            
            # Aggressive cleanup
            if torch.cuda.is_available():
                # Reset CUDA context
                torch.cuda.reset_peak_memory_stats()
                
                # Multiple cache clears
                for _ in range(3):
                    torch.cuda.empty_cache()
                    torch.cuda.synchronize()
            
            # Force Python garbage collection
            for _ in range(3):
                gc.collect()
            
            # Get post-cleanup status
            status_after = self.get_memory_status()
            
            # Log results
            vram_freed = status_before['vram_allocated_gb'] - status_after['vram_allocated_gb']
            ram_freed = status_before['ram_used_gb'] - status_after['ram_used_gb']
            
            logger.info(f"🚨 Emergency cleanup completed")
            logger.info(f"💾 VRAM freed: {vram_freed:.2f} GB")
            logger.info(f"🖥️ RAM freed: {ram_freed:.2f} GB")
            logger.info(f"📊 Emergency count: {self.emergency_count}")
            
            return True
            
        except Exception as e:
            logger.error(f"❌ Emergency cleanup failed: {e}")
            return False
    
    def monitor_and_auto_cleanup(self) -> bool:
        """Monitor memory and trigger automatic cleanup"""
        pressure = self.check_memory_pressure()
        status = self.get_memory_status()
        
        logger.debug(f"📊 Memory pressure: {pressure}")
        logger.debug(f"📱 VRAM: {status['vram_allocated_gb']:.2f}/{status['vram_total_gb']:.2f} GB")
        logger.debug(f"💾 RAM: {status['ram_used_gb']:.2f}/{status['ram_total_gb']:.2f} GB")
        
        if pressure == "EMERGENCY":
            logger.warning("🚨 Emergency memory pressure detected!")
            return self.emergency_cleanup()
        elif pressure == "HIGH":
            logger.info("⚠️ High memory pressure, triggering cleanup")
            return self.cleanup_vram()
        else:
            return False
    
    def get_memory_report(self) -> Dict:
        """Generate comprehensive memory report"""
        status = self.get_memory_status()
        pressure = self.check_memory_pressure()
        
        report = {
            'timestamp': datetime.now().isoformat(),
            'memory_pressure': pressure,
            'vram_status': {
                'allocated_gb': status['vram_allocated_gb'],
                'reserved_gb': status['vram_reserved_gb'],
                'total_gb': status['vram_total_gb'],
                'usage_ratio': status['vram_usage_ratio'],
                'available_gb': status['vram_total_gb'] - status['vram_allocated_gb']
            },
            'ram_status': {
                'used_gb': status['ram_used_gb'],
                'total_gb': status['ram_total_gb'],
                'usage_ratio': status['ram_usage_ratio'],
                'available_gb': status['ram_total_gb'] - status['ram_used_gb']
            },
            'cleanup_stats': {
                'cleanup_count': self.cleanup_count,
                'emergency_count': self.emergency_count,
                'last_cleanup': self.last_cleanup_time.isoformat() if self.last_cleanup_time else None
            },
            'recommendations': self._get_recommendations(pressure, status)
        }
        
        return report
    
    def _get_recommendations(self, pressure: str, status: Dict) -> List[str]:
        """Get memory management recommendations"""
        recommendations = []
        
        if pressure == "EMERGENCY":
            recommendations.extend([
                "🚨 CRITICAL: Stop all processing immediately",
                "🧹 Force emergency cleanup",
                "🔄 Restart vision worker if needed",
                "📉 Reduce batch size to 1"
            ])
        elif pressure == "HIGH":
            recommendations.extend([
                "⚠️ Reduce batch processing",
                "🧹 Trigger cleanup",
                "📊 Monitor memory closely",
                "🔄 Consider model restart"
            ])
        elif pressure == "MEDIUM":
            recommendations.extend([
                "📊 Monitor memory usage",
                "🧹 Periodic cleanup recommended",
                "📉 Consider smaller batches"
            ])
        else:
            recommendations.extend([
                "✅ Memory usage optimal",
                "📊 Continue monitoring"
            ])
        
        # VRAM-specific recommendations
        vram_ratio = status['vram_usage_ratio']
        if vram_ratio > 0.8:
            recommendations.append("📱 VRAM usage high - consider CPU processing")
        elif vram_ratio > 0.6:
            recommendations.append("📱 VRAM usage moderate - batch carefully")
        
        return recommendations

# Global kill switch instance
_kill_switch = None

def get_kill_switch() -> VisionKillSwitch:
    """Get singleton kill switch instance"""
    global _kill_switch
    if _kill_switch is None:
        config = MemoryConfig()
        _kill_switch = VisionKillSwitch(config)
    return _kill_switch

# Convenience functions
def check_memory_pressure() -> str:
    """Check current memory pressure"""
    ks = get_kill_switch()
    return ks.check_memory_pressure()

def cleanup_memory(force: bool = False) -> bool:
    """Trigger memory cleanup"""
    ks = get_kill_switch()
    return ks.cleanup_vram(force)

def emergency_memory_cleanup() -> bool:
    """Trigger emergency cleanup"""
    ks = get_kill_switch()
    return ks.emergency_cleanup()

def get_memory_report() -> Dict:
    """Get memory status report"""
    ks = get_kill_switch()
    return ks.get_memory_report()

if __name__ == "__main__":
    # Test the kill switch
    logger.info("🧪 Testing Vision Kill Switch...")
    
    try:
        ks = get_kill_switch()
        
        # Get memory report
        report = ks.get_memory_report()
        
        logger.info("📊 Memory Report:")
        logger.info(f"   Pressure: {report['memory_pressure']}")
        logger.info(f"   VRAM: {report['vram_status']['usage_ratio']:.1%}")
        logger.info(f"   RAM: {report['ram_status']['usage_ratio']:.1%}")
        
        # Test cleanup
        if report['memory_pressure'] in ["HIGH", "EMERGENCY"]:
            logger.info("🧹 Triggering cleanup...")
            ks.monitor_and_auto_cleanup()
        
        logger.info("✅ Kill switch test completed")
        
    except Exception as e:
        logger.error(f"❌ Kill switch test failed: {e}")
        raise
