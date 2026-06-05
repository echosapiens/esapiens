"""Tests for security module — pure logic, no mocks.

Tests JWT token creation/validation and CLI sanitization.
"""

from app.security import create_access_token, decode_access_token, sanitize_cli_command


class TestJWT:
    """JWT token creation and validation."""

    def test_create_and_decode(self):
        """A created token can be decoded to reveal the original data."""
        data = {"sub": "test-user", "role": "admin"}
        token = create_access_token(data)
        assert isinstance(token, str)
        assert len(token) > 20

        decoded = decode_access_token(token)
        assert decoded is not None
        assert decoded["sub"] == "test-user"
        assert decoded["role"] == "admin"

    def test_decode_invalid_token(self):
        """An invalid token returns None."""
        assert decode_access_token("invalid-token") is None
        assert decode_access_token("") is None

    def test_decode_expired_token(self):
        """An expired token returns None."""
        from datetime import timedelta
        data = {"sub": "test"}
        token = create_access_token(data, expires_delta=timedelta(seconds=-1))
        assert decode_access_token(token) is None

    def test_token_contains_expiry(self):
        """Created tokens include an 'exp' claim."""
        data = {"sub": "test"}
        token = create_access_token(data)
        decoded = decode_access_token(token)
        assert decoded is not None
        assert "exp" in decoded


class TestSanitizeCliCommand:
    """sanitize_cli_command strips dangerous shell characters."""

    def test_backticks_removed(self):
        assert sanitize_cli_command("echo `whoami`") == "echo whoami"

    def test_command_substitution_removed(self):
        assert sanitize_cli_command("echo $(whoami)") == "echo"

    def test_safe_command_unchanged(self):
        cmd = "samtools flagstat /data/input/input.bam > /data/output/flagstat.txt"
        assert sanitize_cli_command(cmd) == cmd

    def test_pipes_allowed(self):
        cmd = "samtools view -h input.bam | grep 'chr1'"
        assert sanitize_cli_command(cmd) == cmd

    def test_redirects_allowed(self):
        cmd = "mafft /data/input/seq.fasta > /data/output/alignment.aln 2> /data/output/mafft.log"
        assert sanitize_cli_command(cmd) == cmd

    def test_trailing_whitespace_stripped(self):
        assert sanitize_cli_command("  echo hello  ") == "echo hello"

    def test_empty_string(self):
        assert sanitize_cli_command("") == ""

    def test_only_whitespace(self):
        assert sanitize_cli_command("   ") == ""
