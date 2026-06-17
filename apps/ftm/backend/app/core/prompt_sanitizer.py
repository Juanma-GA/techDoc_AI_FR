"""Prompt sanitization to prevent LLM injection attacks.

Implements multiple defense layers:
1. Input validation (length, format)
2. Suspicious pattern detection
3. Content filtering
4. Delimiter injection prevention
"""

from __future__ import annotations

import logging
import re
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    pass

logger = logging.getLogger(__name__)


class PromptInjectionError(Exception):
    """Raised when prompt injection is detected."""
    pass


# Patterns that indicate potential prompt injection attempts
SUSPICIOUS_PATTERNS = [
    # Direct instruction override attempts
    re.compile(r"ignore\s+(all\s+)?previous\s+instructions?", re.IGNORECASE),
    re.compile(r"forget\s+(all\s+)?previous\s+(instructions?|commands?)", re.IGNORECASE),
    re.compile(r"disregard\s+(all\s+)?previous\s+instructions?", re.IGNORECASE),
    
    # Role manipulation
    re.compile(r"you\s+are\s+now\s+(a\s+)?", re.IGNORECASE),
    re.compile(r"act\s+as\s+(a\s+)?", re.IGNORECASE),
    re.compile(r"pretend\s+(to\s+be|you\s+are)", re.IGNORECASE),
    re.compile(r"simulate\s+(being\s+)?(a\s+)?", re.IGNORECASE),
    
    # System prompt extraction
    re.compile(r"(show|reveal|display|print)\s+(me\s+)?(your|the)\s+system\s+prompt", re.IGNORECASE),
    re.compile(r"what\s+(is|are)\s+your\s+(initial\s+)?instructions?", re.IGNORECASE),
    
    # Delimiter injection (trying to close assistant's response)
    re.compile(r"<\|.*?\|>"),  # Special tokens
    re.compile(r"\[INST\]|\[/INST\]"),  # Instruction delimiters
    re.compile(r"<assistant>|</assistant>", re.IGNORECASE),
    
    # Code execution attempts
    re.compile(r"```\s*(python|javascript|bash)", re.IGNORECASE),
    re.compile(r"exec\s*\(", re.IGNORECASE),
    re.compile(r"eval\s*\(", re.IGNORECASE),
]

# Maximum safe prompt length (characters)
MAX_PROMPT_LENGTH = 5000

# Maximum safe document content length (characters) - more permissive for file contents
MAX_DOCUMENT_LENGTH = 100000


class PromptSanitizer:
    """Sanitizes user input to prevent prompt injection attacks.
    
    Usage:
        sanitizer = PromptSanitizer()
        safe_prompt = sanitizer.sanitize(user_input, context="chat_message")
    """
    
    def __init__(self, strict: bool = False):
        """Initialize sanitizer.
        
        Args:
            strict: If True, raise exception on suspicious content.
                   If False, log warning and allow (with sanitization).
        """
        self.strict = strict
    
    def sanitize(
        self,
        text: str,
        context: str = "user_input",
        max_length: int | None = None,
    ) -> str:
        """Sanitize user input for safe LLM processing.
        
        Args:
            text: User input to sanitize
            context: Context of input (for logging): "chat_message", "document_content", etc.
            max_length: Override default max length
        
        Returns:
            Sanitized text safe for LLM processing
        
        Raises:
            PromptInjectionError: If strict mode and injection detected
            ValueError: If input is invalid
        """
        if not isinstance(text, str):
            raise ValueError(f"Expected str, got {type(text).__name__}")
        
        # Strip whitespace
        text = text.strip()
        
        if not text:
            return text
        
        # 1. Length validation
        max_len = max_length or (MAX_DOCUMENT_LENGTH if "document" in context else MAX_PROMPT_LENGTH)
        if len(text) > max_len:
            logger.warning(
                f"Input truncated from {len(text)} to {max_len} chars",
                extra={"context": context}
            )
            text = text[:max_len]
        
        # 2. Check for suspicious patterns
        detected_patterns = []
        for pattern in SUSPICIOUS_PATTERNS:
            if pattern.search(text):
                detected_patterns.append(pattern.pattern)
        
        if detected_patterns:
            log_msg = f"Suspicious patterns detected in {context}: {detected_patterns}"
            
            if self.strict:
                logger.error(log_msg)
                raise PromptInjectionError(
                    "Potential prompt injection detected. "
                    "Input contains suspicious instruction patterns."
                )
            else:
                logger.warning(log_msg)
        
        # 3. Normalize dangerous sequences (if not strict mode)
        if not self.strict:
            # Replace special tokens with safe equivalents
            text = re.sub(r"<\|.*?\|>", "[REDACTED]", text)
            text = re.sub(r"\[/?INST\]", "[INSTRUCTION]", text, flags=re.IGNORECASE)
            text = re.sub(r"</?assistant>", "[ASSISTANT]", text, flags=re.IGNORECASE)
        
        return text
    
    def sanitize_document(self, content: str, filename: str = "") -> str:
        """Sanitize document content (e.g., from uploaded files).
        
        More permissive than chat messages but still checks for injection.
        
        Args:
            content: Document text content
            filename: Filename for logging
        
        Returns:
            Sanitized document content
        """
        context = f"document:{filename}" if filename else "document_content"
        return self.sanitize(
            content,
            context=context,
            max_length=MAX_DOCUMENT_LENGTH
        )
    
    def check_safe(self, text: str) -> tuple[bool, list[str]]:
        """Check if text is safe without sanitizing.
        
        Args:
            text: Text to check
        
        Returns:
            Tuple of (is_safe, list_of_detected_patterns)
        """
        if not text or len(text) > MAX_PROMPT_LENGTH:
            return False, ["length_exceeded"]
        
        detected = []
        for pattern in SUSPICIOUS_PATTERNS:
            if pattern.search(text):
                detected.append(pattern.pattern[:50])  # Truncate for readability
        
        return len(detected) == 0, detected


# Global instance for convenience
_default_sanitizer = PromptSanitizer(strict=False)


def sanitize_prompt(text: str, context: str = "user_input") -> str:
    """Convenience function using default sanitizer.
    
    Args:
        text: Text to sanitize
        context: Context for logging
    
    Returns:
        Sanitized text
    """
    return _default_sanitizer.sanitize(text, context=context)


def sanitize_document(content: str, filename: str = "") -> str:
    """Convenience function for document sanitization.
    
    Args:
        content: Document content
        filename: Optional filename
    
    Returns:
        Sanitized content
    """
    return _default_sanitizer.sanitize_document(content, filename=filename)
