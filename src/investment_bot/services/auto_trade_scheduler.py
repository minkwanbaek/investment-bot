from dataclasses import dataclass, field
import logging

logger = logging.getLogger(__name__)


@dataclass
class AutoTradeScheduler:
    """
    Priority-based batch scheduler for auto-trade symbol evaluation.
    
    Evaluates top priority symbols every cycle, with remaining symbols
    processed in rotating batches to reduce cycle time.
    """
    all_symbols: list[str]
    priority_count: int = 10
    batch_size: int = 8
    batch_index: int = field(default=0, init=False)
    
    def __post_init__(self):
        self.priority_symbols = self.all_symbols[: self.priority_count]
        self.remaining_symbols = self.all_symbols[self.priority_count :]
        logger.info(
            "AutoTradeScheduler initialized | priority=%d remaining=%d batch_size=%d",
            len(self.priority_symbols),
            len(self.remaining_symbols),
            self.batch_size,
        )
    
    def get_next_batch(self) -> list[str]:
        """
        Return priority symbols + next batch of remaining symbols.
        
        Uses round-robin to cycle through remaining symbols across multiple cycles.
        """
        if not self.remaining_symbols:
            return list(self.priority_symbols)
        
        start = self.batch_index * self.batch_size
        end = start + self.batch_size
        
        if start >= len(self.remaining_symbols):
            self.batch_index = 0
            start = 0
            end = min(self.batch_size, len(self.remaining_symbols))
        
        batch = self.remaining_symbols[start:end]
        
        if end >= len(self.remaining_symbols):
            self.batch_index = 0
        else:
            self.batch_index += 1
        
        result = list(self.priority_symbols) + batch
        logger.debug(
            "get_next_batch | priority=%d batch=%d total=%d batch_index=%d",
            len(self.priority_symbols),
            len(batch),
            len(result),
            self.batch_index,
        )
        return result
    
    def get_priority_symbols(self) -> list[str]:
        """Return only priority symbols (for fast evaluation)."""
        return list(self.priority_symbols)
    
    def get_remaining_symbols(self) -> list[str]:
        """Return all remaining (non-priority) symbols."""
        return list(self.remaining_symbols)
    
    def get_batch_for_remaining(self) -> list[str]:
        """Get next batch from remaining symbols only (without priority)."""
        if not self.remaining_symbols:
            return []
        
        start = self.batch_index * self.batch_size
        end = start + self.batch_size
        
        if start >= len(self.remaining_symbols):
            self.batch_index = 0
            return list(self.remaining_symbols[: self.batch_size])
        
        batch = self.remaining_symbols[start:end]
        
        if end >= len(self.remaining_symbols):
            self.batch_index = 0
        else:
            self.batch_index += 1
        
        return batch
    
    def reset(self) -> None:
        """Reset batch index to start from beginning."""
        self.batch_index = 0
        logger.info("AutoTradeScheduler batch index reset")
