from __future__ import annotations
import base64, mimetypes, os
from dataclasses import dataclass
from pathlib import Path
import requests

_PROJECT_ROOT = Path(__file__).resolve().parents[2]
_DOTENV_LOADED = False


def _load_project_dotenv() -> None:
    """Load repo-root .env into os.environ. Existing process env wins."""
    global _DOTENV_LOADED
    if _DOTENV_LOADED:
        return
    _DOTENV_LOADED = True

    path = _PROJECT_ROOT / ".env"
    if not path.is_file():
        return

    try:
        from dotenv import load_dotenv
    except ImportError as exc:
        raise RuntimeError(
            "reading .env requires python-dotenv: pip install python-dotenv"
        ) from exc

    load_dotenv(path, override=False)

REGION_HOST = {
    "cn-beijing": "{workspace}.cn-beijing.maas.aliyuncs.com",
    "ap-southeast-1": "{workspace}.ap-southeast-1.maas.aliyuncs.com",
    "eu-central-1": "{workspace}.eu-central-1.maas.aliyuncs.com",
    "ap-northeast-1": "{workspace}.ap-northeast-1.maas.aliyuncs.com",
    "us-east-1": "{workspace}.us-east-1.maas.aliyuncs.com",
}

@dataclass(frozen=True)
class BailianConfig:
    api_key: str
    workspace_id: str
    region: str = "cn-beijing"
    base_url: str | None = None
    timeout: float = 120.0

    @classmethod
    def from_env(cls):
        _load_project_dotenv()
        key = os.getenv("DASHSCOPE_API_KEY", "").strip()
        ws = os.getenv("BAILIAN_WORKSPACE_ID", "").strip()
        region = os.getenv("BAILIAN_REGION", "cn-beijing").strip()
        base = os.getenv("BAILIAN_BASE_URL", "").strip() or None
        if not key:
            raise RuntimeError("DASHSCOPE_API_KEY is required")
        if not ws and not base:
            raise RuntimeError("BAILIAN_WORKSPACE_ID or BAILIAN_BASE_URL is required")
        return cls(key, ws, region, base)

    def resolved_base_url(self):
        if self.base_url:
            return self.base_url.rstrip("/")
        if self.region not in REGION_HOST:
            raise ValueError("unknown region; set BAILIAN_BASE_URL explicitly")
        host = REGION_HOST[self.region].format(workspace=self.workspace_id)
        return f"https://{host}/api/v1"

class BailianClient:
    def __init__(self, config: BailianConfig, session=None):
        self.config = config
        self.session = session or requests.Session()

    def post(self, path: str, payload: dict):
        url = self.config.resolved_base_url() + "/" + path.lstrip("/")
        response = self.session.post(
            url,
            headers={
                "Authorization": f"Bearer {self.config.api_key}",
                "Content-Type": "application/json",
            },
            json=payload,
            timeout=self.config.timeout,
        )
        data = response.json()
        if not response.ok or data.get("code"):
            raise RuntimeError(
                f"Bailian error: {data.get('code')} {data.get('message')} "
                f"request_id={data.get('request_id')}"
            )
        return data

def image_ref(value: str) -> str:
    value = value.strip()
    if value.startswith(("https://", "http://", "data:image/")):
        return value
    path = Path(value)
    if not path.exists():
        raise FileNotFoundError(value)
    mime = mimetypes.guess_type(path.name)[0] or "image/png"
    encoded = base64.b64encode(path.read_bytes()).decode("ascii")
    return f"data:{mime};base64,{encoded}"

def video_ref(value: str) -> str:
    value = value.strip()
    if not value.startswith(("https://", "http://")):
        raise ValueError("Bailian qwen3-vl video input requires a reachable URL")
    return value


def qwen_embedding_model() -> str:
    _load_project_dotenv()
    return (
        os.getenv("QWEN_VL_EMBEDDING_MODEL", "qwen3-vl-embedding").strip()
        or "qwen3-vl-embedding"
    )


def qwen_embedding_dimension() -> int:
    _load_project_dotenv()
    raw = os.getenv("QWEN_VL_EMBEDDING_DIMENSION", "1024").strip() or "1024"
    return int(raw)


def qwen_rerank_model() -> str:
    _load_project_dotenv()
    return (
        os.getenv("QWEN_VL_RERANK_MODEL", "qwen3-vl-rerank").strip()
        or "qwen3-vl-rerank"
    )
