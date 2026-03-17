import requests
import time
from typing import Optional, Any

from .types import NSFWOption
from .api_base import BaseDownloaderAPI


class DanbooruDownloaderAPI(BaseDownloaderAPI):
    def __init__(self, settings=None) -> None:
        super().__init__()
        self.endpoint = "https://danbooru.donmai.us"
        self._settings = settings
        self._load_settings()
        self._settings_window = None

    def _load_settings(self) -> None:
        if self._settings:
            self.tags = self._settings.get_preference("danbooru_tags") or ""
            self.login = self._settings.get_preference("danbooru_login") or ""
            self.api_key = self._settings.get_preference("danbooru_api_key") or ""
        else:
            self.tags = ""
            self.login = ""
            self.api_key = ""

    def set_tags(self, tags: str) -> None:
        self.tags = tags

    def get_tags(self) -> str:
        return self.tags

    def _build_tags_query(self, nsfw_mode: NSFWOption) -> str:
        tags = self.tags.strip() if self.tags else ""
        mode = self._normalize_nsfw_mode(nsfw_mode)
        if mode == NSFWOption.BLOCK_NSFW:
            rating_tag = "rating:safe"
        elif mode == NSFWOption.ONLY_NSFW:
            rating_tag = "rating:explicit"
        else:
            rating_tag = None

        if tags and rating_tag:
            return f"{tags} {rating_tag}"
        elif rating_tag:
            return rating_tag
        return tags

    def _normalize_nsfw_mode(self, nsfw_mode: Any) -> NSFWOption:
        if isinstance(nsfw_mode, NSFWOption):
            return nsfw_mode
        for option in NSFWOption:
            if nsfw_mode == option.value:
                return option
        return NSFWOption.BLOCK_NSFW

    def _is_authenticated(self) -> bool:
        return bool(self.login and self.api_key)

    def _rating_matches(self, post: dict, mode: NSFWOption) -> bool:
        rating = post.get("rating")
        if mode == NSFWOption.BLOCK_NSFW:
            return rating == "s"
        if mode == NSFWOption.ONLY_NSFW:
            return rating == "e"
        return True

    def _request_random_post(self, tags: str) -> tuple[Optional[dict], Optional[str]]:
        params = self._build_auth_params()
        if tags:
            params["tags"] = tags

        try:
            print(f"[danbooru] requesting random post with tags='{tags}'")
            r = requests.get(f"{self.endpoint}/posts/random.json", params=params, timeout=10)
        except Exception as e:
            print(f"[danbooru] request failed: {e}")
            return None, "request_error"

        if r.status_code != 200:
            try:
                error_data = r.json()
            except Exception:
                error_data = {}
            message = str(error_data.get("message", "")) if isinstance(error_data, dict) else ""
            error = str(error_data.get("error", "")) if isinstance(error_data, dict) else ""
            print(f"[danbooru] non-200 response: status={r.status_code} error='{error}' message='{message}'")
            if "TagLimitError" in error or "more than 2 tags" in message:
                return None, "tag_limit"
            return None, "http_error"

        try:
            data = r.json()
            if isinstance(data, dict) and data.get("id"):
                return data, None
            print("[danbooru] unexpected response shape from random endpoint")
            return None, "parse_error"
        except Exception as e:
            print(f"[danbooru] failed to parse response: {e}")
            return None, "parse_error"

    def _build_auth_params(self) -> dict[str, str]:
        params: dict[str, str] = {}
        if self.login:
            params["login"] = self.login
        if self.api_key:
            params["api_key"] = self.api_key
        return params

    def get_random_post(self, nsfw_mode: NSFWOption = NSFWOption.BLOCK_NSFW) -> Optional[dict]:
        mode = self._normalize_nsfw_mode(nsfw_mode)
        tags = self._build_tags_query(mode)
        post, reason = self._request_random_post(tags)
        if post:
            self.info = post
            return post

        # Unauthenticated users hit a low tag limit. If rating tag caused it,
        # retry without rating and filter results locally.
        if reason == "tag_limit" and mode != NSFWOption.SHOW_EVERYTHING and not self._is_authenticated():
            raw_tags = self.tags.strip() if self.tags else ""
            if raw_tags:
                print("[danbooru] tag limit hit; retrying without rating tag and filtering locally")
                for _ in range(10):
                    fallback_post, fallback_reason = self._request_random_post(raw_tags)
                    if fallback_post and self._rating_matches(fallback_post, mode):
                        self.info = fallback_post
                        return fallback_post
                    if fallback_reason and fallback_reason != "tag_limit":
                        break

        return None

    def get_image_url(self, nsfw_mode: NSFWOption = NSFWOption.BLOCK_NSFW) -> Optional[str]:
        post = self.get_random_post(nsfw_mode)
        if post:
            return post.get("file_url")
        return None

    def get_artist(self, info: Optional[dict] = None) -> Optional[str]:
        data = info if info else self.info
        if not data:
            return None
        try:
            artist_tags = data.get("tag_string_artist", "")
            if artist_tags:
                return artist_tags.split(" ")[0]
            return None
        except Exception:
            return None

    def get_link(self, info: Optional[dict] = None) -> Optional[str]:
        data = info if info else self.info
        if not data:
            return None
        try:
            post_id = data.get("id")
            if post_id:
                return f"{self.endpoint}/posts/{post_id}"
            return None
        except Exception:
            return None

    def get_filename_suggestion(self, extension: Optional[str], info: Optional[dict] = None) -> str:
        data = info if info else self.info
        if not data:
            post_id = str(int(time.time()))
        else:
            try:
                post_id = str(data.get("id", int(time.time())))
            except Exception:
                post_id = str(int(time.time()))

        if extension:
            return f"danbooru_{post_id}.{extension}"
        return f"danbooru_{post_id}"

    def open_settings_window(self, parent: Any) -> None:
        from gi.repository import Gtk, Adw

        window = Adw.PreferencesWindow()
        window.set_title("Danbooru Settings")
        window.set_modal(True)

        if isinstance(parent, Gtk.Window):
            window.set_transient_for(parent)
        else:
            toplevel = parent.get_ancestor(Gtk.Window)
            if toplevel:
                window.set_transient_for(toplevel)

        page = Adw.PreferencesPage()
        window.add(page)

        group = Adw.PreferencesGroup()
        group.set_title("Tags")
        page.add(group)

        vbox = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        vbox.set_margin_top(12)
        vbox.set_margin_bottom(12)
        vbox.set_margin_start(12)
        vbox.set_margin_end(12)

        title_label = Gtk.Label(label="Search Tags")
        title_label.add_css_class("heading")
        title_label.set_halign(Gtk.Align.START)
        vbox.append(title_label)

        desc_label = Gtk.Label(label="Enter tags separated by spaces (e.g., cat_ears solo)")
        desc_label.add_css_class("caption")
        desc_label.set_halign(Gtk.Align.START)
        desc_label.set_wrap(True)
        vbox.append(desc_label)

        entry = Gtk.Entry()
        entry.set_text(self.tags)
        entry.set_placeholder_text("e.g., cat_ears solo 1girl")
        entry.set_hexpand(True)
        entry.connect("changed", lambda e: self._on_tags_changed(e, window))
        vbox.append(entry)

        row = Adw.PreferencesRow()
        row.set_child(vbox)
        group.add(row)

        auth_group = Adw.PreferencesGroup()
        auth_group.set_title("Authentication (Optional)")
        page.add(auth_group)

        auth_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        auth_box.set_margin_top(12)
        auth_box.set_margin_bottom(12)
        auth_box.set_margin_start(12)
        auth_box.set_margin_end(12)

        auth_desc = Gtk.Label(
            label="Use your Danbooru login and API key for authenticated requests."
        )
        auth_desc.add_css_class("caption")
        auth_desc.set_halign(Gtk.Align.START)
        auth_desc.set_wrap(True)
        auth_box.append(auth_desc)

        login_entry = Gtk.Entry()
        login_entry.set_text(self.login)
        login_entry.set_placeholder_text("Danbooru username")
        login_entry.set_hexpand(True)
        login_entry.connect("changed", self._on_login_changed)
        auth_box.append(login_entry)

        api_key_entry = Gtk.Entry()
        api_key_entry.set_text(self.api_key)
        api_key_entry.set_placeholder_text("Danbooru API key")
        api_key_entry.set_visibility(False)
        api_key_entry.set_input_purpose(Gtk.InputPurpose.PASSWORD)
        api_key_entry.set_hexpand(True)
        api_key_entry.connect("changed", self._on_api_key_changed)
        auth_box.append(api_key_entry)

        auth_row = Adw.PreferencesRow()
        auth_row.set_child(auth_box)
        auth_group.add(auth_row)

        self._settings_window = window
        window.present()

    def _on_tags_changed(self, entry: Any, window: Any) -> None:
        self.tags = entry.get_text()
        if self._settings:
            self._settings.set_preference("danbooru_tags", self.tags)

    def _on_login_changed(self, entry: Any) -> None:
        self.login = entry.get_text()
        if self._settings:
            self._settings.set_preference("danbooru_login", self.login)

    def _on_api_key_changed(self, entry: Any) -> None:
        self.api_key = entry.get_text()
        if self._settings:
            self._settings.set_preference("danbooru_api_key", self.api_key)
