def classify_task_type(pages):
    text = " ".join(p.get("contents", "") for p in pages)

    if "git/trees" in text:
        return "github_tree"
    if "messy.csv" in text:
        return "csv"
    if "uv http get" in text:
        return "uv"
    if "audio-passphrase" in text:
        return "audio"
    if "heatmap.png" in text:
        return "image"

    return "generic"
