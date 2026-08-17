"""Tests for the contract agent — pure logic, no mocks.

Tests command splitting, sanitization, and contract building.
"""

from app.agents.contract import _extract_download_steps, _build_command, _build_download_command
from app.security import sanitize_cli_command


class TestExtractDownloadSteps:
    """_extract_download_steps splits compound commands correctly."""

    def test_pure_tool_command(self):
        """A command with no download steps returns empty download."""
        cmd = "samtools flagstat /data/input/input.bam > /data/output/flagstat.txt"
        download, tool = _extract_download_steps(cmd)
        assert download == ""
        assert "samtools flagstat" in tool

    def test_pure_download_command(self):
        """A command with only download steps returns empty tool."""
        cmd = "python3 -c \"import urllib.request; urllib.request.urlretrieve('https://example.com/file.fasta', '/data/input/file.fasta')\""
        download, tool = _extract_download_steps(cmd)
        assert "python3 -c" in download
        assert tool == cmd  # falls back to full command when no tool parts

    def test_mixed_command(self):
        """A compound command splits correctly."""
        cmd = (
            "python3 -c \"import urllib.request; urllib.request.urlretrieve('https://example.com/reads.fastq', '/data/input/reads.fastq')\""
            " && "
            "samtools flagstat /data/input/reads.fastq > /data/output/flagstat.txt"
        )
        download, tool = _extract_download_steps(cmd)
        assert "python3 -c" in download
        assert "samtools flagstat" in tool

    def test_printf_is_download(self):
        """printf commands are treated as download steps."""
        cmd = "printf '>seq1\\nACGT\\n' > /data/input/seq.fasta && mafft /data/input/seq.fasta > /data/output/alignment.aln"
        download, tool = _extract_download_steps(cmd)
        assert "printf" in download
        assert "mafft" in tool

    def test_curl_is_download(self):
        """curl commands are treated as download steps."""
        cmd = "curl -o /data/input/seq.fasta https://example.com/seq.fasta && blastn -query /data/input/seq.fasta -db /data/input/nt -out /data/output/results.txt"
        download, tool = _extract_download_steps(cmd)
        assert "curl" in download
        assert "blastn" in tool

    def test_wget_is_download(self):
        """wget commands are treated as download steps."""
        cmd = "wget -O /data/input/seq.fasta https://example.com/seq.fasta && muscle -in /data/input/seq.fasta -out /data/output/alignment.aln"
        download, tool = _extract_download_steps(cmd)
        assert "wget" in download
        assert "muscle" in tool

    def test_mkdir_output_is_skipped(self):
        """mkdir -p /data/output is skipped entirely."""
        cmd = "mkdir -p /data/output && samtools flagstat /data/input/input.bam > /data/output/flagstat.txt"
        download, tool = _extract_download_steps(cmd)
        assert download == ""
        assert "samtools flagstat" in tool

    def test_empty_command(self):
        """Empty command returns empty strings."""
        download, tool = _extract_download_steps("")
        assert download == ""
        assert tool == ""

    def test_multiple_downloads(self):
        """Multiple download steps are all captured."""
        cmd = (
            "python3 -c \"import urllib.request; urllib.request.urlretrieve('https://example.com/1.fastq', '/data/input/1.fastq')\""
            " && "
            "python3 -c \"import urllib.request; urllib.request.urlretrieve('https://example.com/2.fastq', '/data/input/2.fastq')\""
            " && "
            "cat /data/input/1.fastq /data/input/2.fastq > /data/input/combined.fastq"
        )
        download, tool = _extract_download_steps(cmd)
        assert download.count("python3 -c") == 2
        assert "cat" in tool


class TestBuildCommand:
    """_build_command extracts tool-only commands from research output."""

    def test_with_generated_command(self):
        output = {"generated_command": "samtools flagstat /data/input/input.bam > /data/output/flagstat.txt"}
        cmd = _build_command(output)
        assert cmd.startswith("mkdir -p /data/output &&")
        assert "samtools flagstat" in cmd

    def test_with_download_and_tool(self):
        output = {
            "generated_command": (
                "python3 -c \"import urllib.request; urllib.request.urlretrieve('https://example.com/r.fastq', '/data/input/r.fastq')\""
                " && "
                "samtools flagstat /data/input/r.fastq > /data/output/flagstat.txt"
            )
        }
        cmd = _build_command(output)
        assert "python3 -c" not in cmd
        assert "samtools flagstat" in cmd

    def test_empty_generated_command(self):
        output = {"generated_command": ""}
        cmd = _build_command(output)
        assert "No command generated" in cmd

    def test_missing_generated_command(self):
        output = {}
        cmd = _build_command(output)
        assert "No command generated" in cmd


class TestBuildDownloadCommand:
    """_build_download_command extracts download-only commands."""

    def test_with_download(self):
        output = {
            "download_commands": [
                "python3 -c \"import urllib.request; urllib.request.urlretrieve('https://example.com/r.fastq', '/data/input/r.fastq')\""
            ],
            "generated_command": "samtools flagstat /data/input/r.fastq > /data/output/flagstat.txt",
        }
        cmd = _build_download_command(output)
        assert cmd.startswith("mkdir -p /data/input &&")
        assert "python3 -c" in cmd
        assert "flagstat" not in cmd

    def test_no_download(self):
        output = {"generated_command": "samtools flagstat /data/input/input.bam > /data/output/flagstat.txt"}
        cmd = _build_download_command(output)
        assert cmd == ""

    def test_empty_generated_command(self):
        output = {"generated_command": ""}
        cmd = _build_download_command(output)
        assert cmd == ""


class TestSanitizeCliCommand:
    """sanitize_cli_command strips dangerous shell characters."""

    def test_backticks_removed(self):
        assert sanitize_cli_command("echo `whoami`") == "echo whoami"

    def test_command_substitution_removed(self):
        assert sanitize_cli_command("echo $(whoami)") == "echo"

    def test_safe_command_unchanged(self):
        cmd = "samtools flagstat /data/input/input.bam > /data/output/flagstat.txt"
        assert sanitize_cli_command(cmd) == cmd

    def test_unsafe_characters_stripped(self):
        cmd = "samtools flagstat input.bam | grep 'chr1'"
        result = sanitize_cli_command(cmd)
        assert "|" in result  # pipes are allowed
        assert "'" in result  # single quotes are allowed

    def test_trailing_whitespace_stripped(self):
        assert sanitize_cli_command("  echo hello  ") == "echo hello"
