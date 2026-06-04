"""hw_proxy pydentic shemas module"""
import re

# pylint: disable=line-too-long


class ValidationConstants:
    """
    A collection of regular expression constants
    used for validating configuration values.

    These include patterns for validating
    host/domain names, URLs, paths, project names,
    slugs, passwords, secret keys, and MySQL names.
    """
    #: Matches a host/domain (e.g., "localhost",
    # an IPv4 address with an optional port,
    # or a standard domain)
    HOST_REGEX: re.Pattern = re.compile(
        r"^(localhost|((\d{1,3}\.){3}\d{1,3}(:\d{1,5})?)|([A-Za-z0-9-]+\.[A-Za-z0-9-.]+)|([A-Za-z0-9-_]+))$"
    )
    #: Matches an HTTP or HTTPS URL with a valid
    # host/domain and an optional port.
    HTTP_HOST_REGEX: re.Pattern = re.compile(
        r"^https?:\/\/(?:localhost|(?:\d{1,3}\.){3}\d{1,3}|(?:[A-Za-z0-9-]+\.)+[A-Za-z]{2,})(?::\d{1,5})?$"
    )
    #: Matches a URL path that must start with a slash
    # and can contain allowed URL characters.
    URL_PATH_STR_REGEX: re.Pattern = re.compile(r"^\/?[A-Za-z0-9\-._~\/]*$")
    #: Matches an alphanumeric key that can include underscores and hyphens
    # (used for project names, etc.).
    KEY_REGEX: re.Pattern = re.compile(r"^[A-Za-z0-9_-]+$")
    #: Matches a slug: lowercase letters, digits, and hyphens
    # (e.g., "my-project-123").
    SLUG_REGEX: re.Pattern = re.compile(r"^[a-z0-9-]+$")
    #: Matches a Unix-style absolute path
    # containing letters, digits, underscores, hyphens, and slashes.
    UNIX_PATH_REGEX: re.Pattern = re.compile(r"^\/[A-Za-z0-9_\-\/]+$")
    #: Matches a absolute path containing letters,
    # digits, underscores, hyphens, ':', and slashes.
    FILE_PATH_REGEX: re.Pattern = re.compile(r"^(?:\/|(?:[A-Z]:))[A-Za-z0-9_\-\/\\:]+$")
    #: Validates that a password has at least 8 characters,
    # including at least one lowercase letter,
    #: one uppercase letter, one digit,
    # and one special character, and excludes spaces.
    PASSWORD_REGEX: re.Pattern = re.compile(r"^(?=.*[a-z])(?=.*[A-Z])(?=.*\d)(?=.*[\W_])(?!.*\s).{8,}$")
    #: Validates that a secret key is at least 32 characters
    # long and includes mixed-case letters,
    #: digits, and special characters.
    SECRET_KEY_REGEX: re.Pattern = re.compile(r"^(?=.*[a-z])(?=.*[A-Z])(?=.*\d)(?=.*[-_])[A-Za-z\d\-_]{32,}$")
    #: Matches MySQL names (database and user names),
    # which may only contain letters, digits, and underscores.
    MYSQL_NAME_REGEX: re.Pattern = re.compile(r"^[A-Za-z0-9_]+$")
    # Regex pattern to match invisible/control Unicode characters,
    # including zero-width spaces (U+200B-U+200D), BOM (U+FEFF),
    # and standard C0/C1 control codes, while preserving newlines,
    # carriage returns, and tabs.
    CONTROL_CHAR_PATTERN: re.Pattern = re.compile(
        r"[\u0000-\u0008\u000B-\u000C\u000E-\u001F"
        r"\u007F-\u009F\u200B-\u200D\uFEFF]"
    )

    @classmethod
    def remove_invisible_chars(cls, text: str) -> str:
        """
        Strip invisible or control Unicode characters from a string,
        preserving line breaks and tabs.

        Args:
            text: Input text potentially containing invisibles.

        Returns:
            Cleaned text without control or zero-width chars.
        """
        return cls.CONTROL_CHAR_PATTERN.sub('', text)
