from dataclasses import dataclass
from typing import List, Optional, Dict, Any
from enum import Enum
import json
import os
from typing_extensions import TypeAlias
import datetime

class PromptManager:
    def __init__(self):
        self.messages: List[Dict[str, Any]] = []
        self.keep_context = True
        self.system_message = {
            "role": "system",
            "content": "You are an AI assistant that generates shell scripts based on task descriptions. Generate only the script code without explanations or markdown formatting.",
            "timestamp": datetime.datetime.now()
        }

    def add_message(self, role: str, content: str, keep: Optional[bool] = None):
        """Add a single message to history"""
        if keep is None:
            keep = self.keep_context

        if keep:
            self.messages.append({
                "role": role,
                "content": content,
                "timestamp": datetime.datetime.now()
            })

    def pop_message(self):
        """Remove the last message from history"""
        if self.messages:
            return self.messages.pop()
        return None

    def get_messages(self, num_previous: Optional[int] = None) -> List[Dict[str, str]]:
        """Get message history in OpenAI API format"""
        formatted_messages = [
            {"role": self.system_message["role"],
             "content": self.system_message["content"]}
        ]

        if not self.messages:
            return formatted_messages

        if num_previous is not None:
            history_subset = self.messages[-num_previous:]
        else:
            history_subset = self.messages

        formatted_messages.extend(
            {"role": msg["role"], "content": msg["content"]}
            for msg in history_subset
        )

        return formatted_messages

    def clear_history(self):
        """Clear conversation history but keep system message"""
        self.messages = []

    def set_keep_context(self, keep_context: bool):
        self.keep_context = keep_context

    def set_system_message(self, content: str):
        """Update the system message"""
        self.system_message = {
            "role": "system",
            "content": content,
            "timestamp": datetime.datetime.now()
        }

    def get_last_message(self, role: Optional[str] = None) -> Optional[str]:
        """Get the most recent message content for given role"""
        for msg in reversed(self.messages):
            if role is None or msg["role"] == role:
                return msg["content"]
        return None

    @property
    def context_length(self) -> int:
        """Get number of messages in history"""
        return len(self.messages)

    def save_history(self, path: str):
        """Save conversation history to a file"""
        with open(path, "w", encoding="utf-8") as file:
            # save messages (role, content) and system message
            messages_filtered = [{"role": msg["role"], "content": msg["content"]} for msg in self.messages]
            system_message_filtered = {
                "role": self.system_message["role"],
                "content": self.system_message["content"]
            }
            json_data = {
                "messages": messages_filtered,
                "system_message": system_message_filtered
            }
            json.dump(json_data, file, ensure_ascii=False, indent=2)
