"""SSOT体系化 P1: .dir-manifest.json 操作中核モジュール."""
import hashlib
import unicodedata


def meaning_hash(meaning: str) -> str:
    """meaning文字列をSHA-256先頭8桁に正規化hash化（NFKC・trim・lower）.

    Args:
        meaning: ハッシュ対象の意味文字列。

    Returns:
        SHA-256 の先頭8桁16進数。
    """
    normalized = unicodedata.normalize("NFKC", meaning).strip().lower()
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()[:8]


def validate_manifest(manifest: dict) -> None:
    """manifest の基本バリデーション（重複 path・空 meaning）.

    Args:
        manifest: ``.dir-manifest.json`` 相当の dict。

    Raises:
        ValueError: 重複 path または空 meaning が存在する場合。
    """
    directories = manifest.get("directories", [])
    paths = [d["path"] for d in directories]
    if len(paths) != len(set(paths)):
        raise ValueError("duplicate path in directories")
    for d in directories:
        if not d.get("meaning", "").strip():
            raise ValueError(f"empty meaning for path: {d['path']}")
