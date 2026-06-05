"""Tests for the intent classifier — pure logic, no mocks."""

from app.intent import classify_intent


class TestClassifyIntent:
    """classify_intent() distinguishes casual chat from pipeline requests."""

    def test_short_greeting_is_chat(self):
        """Messages of 2 words or fewer are always chat."""
        assert classify_intent("hey") == "chat"
        assert classify_intent("hello there") == "chat"
        assert classify_intent("hi") == "chat"
        assert classify_intent("thanks") == "chat"
        assert classify_intent("ok") == "chat"

    def test_casual_question_is_chat(self):
        """Casual questions without pipeline keywords are chat."""
        assert classify_intent("how are you") == "chat"
        assert classify_intent("what can you do") == "chat"
        assert classify_intent("tell me a joke") == "chat"
        assert classify_intent("who are you") == "chat"

    def test_single_keyword_short_is_chat(self):
        """Single keyword in a 3-word message is pipeline (keyword + 3+ words = pipeline)."""
        assert classify_intent("run that again") == "pipeline"
        assert classify_intent("map the data") == "pipeline"

    def test_single_keyword_longer_is_pipeline(self):
        """Single keyword in a 3+ word message is pipeline."""
        assert classify_intent("can you align these sequences") == "pipeline"
        assert classify_intent("run a blast search") == "pipeline"
        assert classify_intent("quantify my rna seq data") == "pipeline"

    def test_two_keywords_is_pipeline(self):
        """Two or more keywords always trigger pipeline."""
        assert classify_intent("align my fastq reads") == "pipeline"
        assert classify_intent("run star alignment on rna seq") == "pipeline"
        assert classify_intent("samtools flagstat on bam file") == "pipeline"
        assert classify_intent("trim fastq with trimmomatic") == "pipeline"

    def test_tool_name_is_pipeline(self):
        """Explicit tool names trigger pipeline."""
        assert classify_intent("run mafft on my sequences") == "pipeline"
        assert classify_intent("use bwa for alignment") == "pipeline"
        assert classify_intent("run salmon quantification") == "pipeline"
        assert classify_intent("fastqc quality check") == "pipeline"

    def test_mixed_case_is_case_insensitive(self):
        """Classification is case-insensitive."""
        assert classify_intent("Run STAR on RNA-Seq data") == "pipeline"
        assert classify_intent("ALIGN SEQUENCES WITH MAFFT") == "pipeline"

    def test_whitespace_handling(self):
        """Leading/trailing whitespace is stripped."""
        assert classify_intent("  align my fastq reads  ") == "pipeline"
        assert classify_intent("  hey  ") == "chat"

    def test_empty_or_whitespace_only(self):
        """Empty or whitespace-only messages are chat."""
        assert classify_intent("") == "chat"
        assert classify_intent("   ") == "chat"

    def test_pipeline_keyword_in_question(self):
        """Questions containing pipeline keywords are pipeline."""
        assert classify_intent("can you do a differential expression analysis") == "pipeline"
        assert classify_intent("how do i quantify transcripts with salmon") == "pipeline"

    def test_ambiguous_terms(self):
        """Terms like 'run' alone are not enough to trigger pipeline in short messages."""
        assert classify_intent("run that") == "chat"
        assert classify_intent("just run it") == "pipeline"  # 3 words + 'run' keyword = pipeline
