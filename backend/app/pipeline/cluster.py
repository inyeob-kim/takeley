from dataclasses import dataclass, field
from datetime import datetime

from app.pipeline.dedupe import is_near_duplicate
from app.pipeline.normalize import content_fingerprint, normalize_text


@dataclass
class ClusterItem:
    raw_id: str
    text: str
    url: str | None = None
    provider: str = "unknown"
    published_at: datetime | None = None


@dataclass
class Cluster:
    key: str
    texts: list[str] = field(default_factory=list)
    raw_ids: list[str] = field(default_factory=list)
    urls: list[str] = field(default_factory=list)
    providers: list[str] = field(default_factory=list)
    items: list[ClusterItem] = field(default_factory=list)

    @property
    def unique_providers(self) -> list[str]:
        return list(dict.fromkeys(self.providers))

    @property
    def earliest_published_at(self) -> datetime | None:
        times = [i.published_at for i in self.items if i.published_at is not None]
        return min(times) if times else None


def cluster_items(
    items: list[ClusterItem] | list[tuple],
    similarity: float = 0.82,
) -> list[Cluster]:
    """Cluster raw items into event groups by near-duplicate text."""
    normalized_items: list[ClusterItem] = []
    for item in items:
        if isinstance(item, ClusterItem):
            normalized_items.append(item)
        else:
            # Back-compat: (raw_id, text, url) or (raw_id, text, url, provider)
            raw_id, text = item[0], item[1]
            url = item[2] if len(item) > 2 else None
            provider = item[3] if len(item) > 3 else "unknown"
            normalized_items.append(
                ClusterItem(raw_id=raw_id, text=text, url=url, provider=provider)
            )

    clusters: list[Cluster] = []
    for item in normalized_items:
        norm = normalize_text(item.text)
        matched: Cluster | None = None
        for cluster in clusters:
            if any(is_near_duplicate(norm, t, similarity) for t in cluster.texts):
                matched = cluster
                break
        if matched is None:
            key = content_fingerprint(norm)[:16]
            matched = Cluster(key=key)
            clusters.append(matched)
        matched.texts.append(norm)
        matched.raw_ids.append(item.raw_id)
        matched.providers.append(item.provider)
        matched.items.append(item)
        if item.url:
            matched.urls.append(item.url)
    return clusters
