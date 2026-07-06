import requests


MAX_IMAGE_SIZE_BYTES = 10 * 1024 * 1024
REQUEST_TIMEOUT_SECONDS = 15


def download_image(url: str) -> tuple[bytes, str]:
    if not url:
        raise ValueError("Image URL is missing.")

    try:
        with requests.get(
            url,
            timeout=REQUEST_TIMEOUT_SECONDS,
            allow_redirects=True,
            stream=True,
        ) as response:
            if response.status_code != 200:
                raise ValueError("Image download failed with an invalid response.")

            content_type = response.headers.get("content-type", "").split(";")[0].strip()
            if not content_type.startswith("image/"):
                raise ValueError("Downloaded URL did not return an image.")

            chunks: list[bytes] = []
            total_size = 0

            for chunk in response.iter_content(chunk_size=8192):
                if not chunk:
                    continue

                total_size += len(chunk)
                if total_size > MAX_IMAGE_SIZE_BYTES:
                    raise ValueError("Image is too large. Maximum allowed size is 10 MB.")

                chunks.append(chunk)

            return b"".join(chunks), content_type
    except requests.Timeout as exc:
        raise ValueError("Image download timed out.") from exc
    except requests.RequestException as exc:
        raise ValueError("Image download request failed.") from exc
