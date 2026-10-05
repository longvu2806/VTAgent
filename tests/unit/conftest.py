import pytest
from tokenizers import Tokenizer
from tokenizers.models import WordLevel
from tokenizers.pre_tokenizers import WhitespaceSplit


@pytest.fixture
def word_tokenizer() -> Tokenizer:
    """Offline stand-in for the bge-m3 tokenizer: one token per whitespace-separated word."""
    tokenizer = Tokenizer(WordLevel({"[UNK]": 0}, unk_token="[UNK]"))
    tokenizer.pre_tokenizer = WhitespaceSplit()
    return tokenizer
