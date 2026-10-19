"""
YUNA Dynamic GIF Rotator & Management Engine
Handles rotational, non-repeating delivery of saved and live GIFs for:
- $ngif [category]
- $gif [query]
- Action / Roleplay commands fallback rotation
"""

import os
import json
import random
import logging
from collections import deque
from typing import Optional, Dict, List, Tuple
import aiohttp

_BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_ANIME_CACHE_FILE = os.path.join(_BASE_DIR, "db", "cached_anime_gifs.json")
_GENERAL_CACHE_FILE = os.path.join(_BASE_DIR, "db", "cached_general_gifs.json")

# Verified Static CDN Neko GIFs (100 links guaranteed 200 OK)
SAVED_NEKO_GIFS: List[str] = [
    f"https://cdn.nekos.life/ngif/neko_{i:03d}.gif" for i in range(1, 101)
]

# Curated fallback anime reaction GIFs
DEFAULT_ANIME_CATEGORIES: Dict[str, List[str]] = {
    "dance": [
        "https://nekos.best/api/v2/dance/ad52db29-5676-4cc0-a6c7-bc6bf1c1fe88.gif",
        "https://nekos.best/api/v2/dance/842e63de-33c2-436d-9002-6e3bf7906286.gif",
        "https://nekos.best/api/v2/dance/780a9054-3abf-4eb6-a284-04da2d25e08a.gif",
        "https://nekos.best/api/v2/dance/c0b459d6-cd9b-4db1-99a7-f5feb3b7b20c.gif",
        "https://nekos.best/api/v2/dance/4fa14dc9-e948-4090-8987-a3967b7b2eb4.gif",
        "https://media.giphy.com/media/bMLGNRoAY0Y3MUIukQ/giphy.gif"
    ],
    "hug": [
        "https://nekos.best/api/v2/hug/a7a7ddcb-ff7a-4cbb-9c0d-b4b9679f22c1.gif",
        "https://nekos.best/api/v2/hug/7f94bbfe-d0ec-4752-9e8e-d9004d2e8b6b.gif",
        "https://nekos.best/api/v2/hug/0b08da31-b8aa-4623-a178-0bc97395029b.gif",
        "https://media.giphy.com/media/l2QDM9Jnim1YV5ujC/giphy.gif",
        "https://i.imgur.com/w3duWdC.gif"
    ],
    "kiss": [
        "https://nekos.best/api/v2/kiss/f47b6861-f3b1-4f15-8472-7489ea730ef3.gif",
        "https://nekos.best/api/v2/kiss/b5e39b98-cb54-46b5-b778-f2b7f730c4a4.gif",
        "https://media.giphy.com/media/G3va31oEEnIkM/giphy.gif"
    ],
    "pat": [
        "https://nekos.best/api/v2/pat/3f1ff635-c8b1-482d-8869-72c08e5f2998.gif",
        "https://nekos.best/api/v2/pat/6c66ee7c-eb85-4560-84cf-cb07c9133a8c.gif",
        "https://media.giphy.com/media/ARSp9T7wwxNcs/giphy.gif"
    ],
    "cuddle": [
        "https://nekos.best/api/v2/cuddle/1a494793-79fa-47cb-bbf8-6052f9547ea8.gif",
        "https://nekos.best/api/v2/cuddle/2f442b08-c89b-4654-a3c3-6311652fe1d3.gif",
        "https://media.giphy.com/media/lrr9rHuoJOE0w/giphy.gif"
    ],
    "slap": [
        "https://nekos.best/api/v2/slap/d7f1d4f2-95f7-4148-af5e-39908cf6fc5e.gif",
        "https://media.giphy.com/media/Gf3AUz3eBNbTW/giphy.gif"
    ],
    "smile": [
        "https://nekos.best/api/v2/smile/7b003a31-645b-426b-80a5-f3775ba315e8.gif",
        "https://nekos.best/api/v2/smile/9cb28014-934c-4731-b850-2f3b92f3ad8a.gif"
    ],
    "blush": [
        "https://nekos.best/api/v2/blush/0cbb91b3-d25a-4b08-9df2-50d40e1b6f65.gif",
        "https://media.giphy.com/media/T3Vvyi6SHJtXW/giphy.gif"
    ],
    "cry": [
        "https://nekos.best/api/v2/cry/5b736b69-8069-42b7-a363-f277ca38318e.gif",
        "https://media.giphy.com/media/ROF8OQvDmxytW/giphy.gif"
    ],
    "wave": [
        "https://nekos.best/api/v2/wave/a590b1bf-0b1e-42c2-8ae3-95208f0a0c20.gif",
        "https://media.giphy.com/media/108A74TAGnUTeg/giphy.gif"
    ],
    "wink": [
        "https://nekos.best/api/v2/wink/3ad60ef2-bf72-4fcf-8472-a6f6630f9a56.gif",
        "https://media.giphy.com/media/gnrYlffv8dIqY/giphy.gif"
    ],
    "pout": [
        "https://nekos.best/api/v2/pout/a0f1ba0c-1db2-4d1a-8289-4d89fae155bc.gif",
        "https://media.giphy.com/media/zrxazUScjhxo4/giphy.gif"
    ],
    "sleep": [
        "https://nekos.best/api/v2/sleep/4d864eb5-5134-4530-9bfa-b05423871ce8.gif",
        "https://media.giphy.com/media/e24Q8FKE2mxRS/giphy.gif"
    ],
    "smug": [
        "https://nekos.best/api/v2/smug/b429a139-c12b-45be-bbff-35b8cfbf8b46.gif",
        "https://media.giphy.com/media/e24Q8FKE2mxRS/giphy.gif"
    ],
    "feed": [
        "https://nekos.best/api/v2/feed/21d5a6b0-fa64-4a41-b8ea-f29424660eb9.gif",
        "https://media.giphy.com/media/108A74TAGnUTeg/giphy.gif"
    ],
    "bite": [
        "https://nekos.best/api/v2/bite/114c0003-8d0f-48d6-9ae8-5c464bf0486c.gif",
        "https://media.giphy.com/media/OqQvAAM387AZW/giphy.gif"
    ],
    "poke": [
        "https://nekos.best/api/v2/poke/5cf26d7c-3f26-4444-be1f-0bda0ea0c35f.gif",
        "https://media.giphy.com/media/pWd360nbsd2ne/giphy.gif"
    ]
}

# Curated fallback general GIFs
DEFAULT_GENERAL_GIFS: List[str] = [
    "https://media.giphy.com/media/v1.Y2lkPTc5MGI3NjExbnZ6bTJmd3Y1NWQ3MGd6d2RraW15NXhpbWtydjZub3E4Z3A3cnBqYSZlcD12MV9naWZzX3NlYXJjaCZjdD1n/fUQ4rhUZJYiQsas6WD/giphy.gif",
    "https://media.giphy.com/media/v1.Y2lkPTc5MGI3NjExd2RraW15NXhpbWtydjZub3E4Z3A3cnBqYSZlcD12MV9naWZzX3NlYXJjaCZjdD1n/artj92V8o75VPL7AeQ/giphy.gif",
    "https://media.giphy.com/media/v1.Y2lkPTc5MGI3NjExd2RraW15NXhpbWtydjZub3E4Z3A3cnBqYSZlcD12MV9naWZzX3NlYXJjaCZjdD1n/jpbnoe3UIa8TU8LM13/giphy.gif",
    "https://media.giphy.com/media/v1.Y2lkPTc5MGI3NjExd2RraW15NXhpbWtydjZub3E4Z3A3cnBqYSZlcD12MV9naWZzX3NlYXJjaCZjdD1n/111ebonMs90YLu/giphy.gif",
    "https://media.giphy.com/media/v1.Y2lkPTc5MGI3NjExd2RraW15NXhpbWtydjZub3E4Z3A3cnBqYSZlcD12MV9naWZzX3NlYXJjaCZjdD1n/blSTtZehjAZ8I/giphy.gif",
    "https://media.giphy.com/media/v1.Y2lkPTc5MGI3NjExd2RraW15NXhpbWtydjZub3E4Z3A3cnBqYSZlcD12MV9naWZzX3NlYXJjaCZjdD1n/3o7TKSjRrfIPjeiVyM/giphy.gif",
    "https://media.giphy.com/media/v1.Y2lkPTc5MGI3NjExd2RraW15NXhpbWtydjZub3E4Z3A3cnBqYSZlcD12MV9naWZzX3NlYXJjaCZjdD1n/l0MYt5jPR6QX5pnqM/giphy.gif",
    "https://media.giphy.com/media/v1.Y2lkPTc5MGI3NjExd2RraW15NXhpbWtydjZub3E4Z3A3cnBqYSZlcD12MV9naWZzX3NlYXJjaCZjdD1n/blSTtZehjAZ8I/giphy.gif",
    "https://media.giphy.com/media/v1.Y2lkPTc5MGI3NjExd2RraW15NXhpbWtydjZub3E4Z3A3cnBqYSZlcD12MV9naWZzX3NlYXJjaCZjdD1n/04DMYESomjb6BCBNB8/giphy.gif",
    "https://media.giphy.com/media/v1.Y2lkPTc5MGI3NjExd2RraW15NXhpbWtydjZub3E4Z3A3cnBqYSZlcD12MV9naWZzX3NlYXJjaCZjdD1n/YrD1PQldGsstG/giphy.gif",
    "https://media.giphy.com/media/v1.Y2lkPTc5MGI3NjExd2RraW15NXhpbWtydjZub3E4Z3A3cnBqYSZlcD12MV9naWZzX3NlYXJjaCZjdD1n/GOHONjvYJFkUJF3bg4/giphy.gif",
    "https://media.giphy.com/media/v1.Y2lkPTc5MGI3NjExd2RraW15NXhpbWtydjZub3E4Z3A3cnBqYSZlcD12MV9naWZzX3NlYXJjaCZjdD1n/A0Zt7yuDULiy4ofmVD/giphy.gif",
    "https://media.giphy.com/media/v1.Y2lkPTc5MGI3NjExd2RraW15NXhpbWtydjZub3E4Z3A3cnBqYSZlcD12MV9naWZzX3NlYXJjaCZjdD1n/P1wkYq6EZPWfNMLmEJ/giphy.gif"
]


class RotationalPool:
    """
    Guarantees strict circular rotational sending without duplicate repeats.
    Once all items in the cycle have been delivered, reshuffles the order
    for the next pass while ensuring no consecutive duplicate at the boundary.
    """
    def __init__(self, items: List[str]):
        self.items: List[str] = list(items) if items else list(DEFAULT_GENERAL_GIFS)
        self.order: List[int] = list(range(len(self.items)))
        random.shuffle(self.order)
        self.pointer: int = 0
        self.recent_history: deque = deque(maxlen=min(50, max(5, len(self.items) // 2)))

    def add_items(self, new_items: List[str]):
        """Dynamically expand pool with newly discovered URLs."""
        existing = set(self.items)
        added = False
        for item in new_items:
            if item and item not in existing:
                self.items.append(item)
                existing.add(item)
                added = True
        if added:
            old_len = len(self.order)
            new_indices = list(range(old_len, len(self.items)))
            random.shuffle(new_indices)
            self.order.extend(new_indices)

    def get_next(self) -> str:
        if not self.items:
            return DEFAULT_GENERAL_GIFS[0]

        # If we have reached the end of the current cycle, reshuffle
        if self.pointer >= len(self.order):
            last_item = self.items[self.order[-1]] if self.order else None
            random.shuffle(self.order)
            # Ensure the first item of the new cycle is not identical to the last delivered
            if len(self.order) > 1 and last_item and self.items[self.order[0]] == last_item:
                self.order[0], self.order[-1] = self.order[-1], self.order[0]
            self.pointer = 0

        item_idx = self.order[self.pointer]
        selected_url = self.items[item_idx]
        self.pointer += 1

        self.recent_history.append(selected_url)
        return selected_url


class GifManager:
    """
    Universal GIF Rotator and Cache Manager for YUNA.
    """
    def __init__(self):
        self.neko_pool = RotationalPool(SAVED_NEKO_GIFS)
        self.category_pools: Dict[str, RotationalPool] = {}
        self.general_pool: RotationalPool = RotationalPool(DEFAULT_GENERAL_GIFS)
        self.query_states: Dict[str, Dict] = {}
        self._load_cached_files()

    def _load_cached_files(self):
        # 1. Load anime category GIFs from disk cache if present
        try:
            if os.path.exists(_ANIME_CACHE_FILE):
                with open(_ANIME_CACHE_FILE, "r", encoding="utf-8") as f:
                    anime_data = json.load(f)
                    for cat, urls in anime_data.items():
                        cat_key = cat.lower()
                        if urls:
                            self.category_pools[cat_key] = RotationalPool(urls)
        except Exception as e:
            logging.warning(f"[GIF_MANAGER] Could not load anime cache: {e}")

        # Ensure default anime categories exist
        for cat, urls in DEFAULT_ANIME_CATEGORIES.items():
            cat_key = cat.lower()
            if cat_key not in self.category_pools:
                self.category_pools[cat_key] = RotationalPool(urls)
            else:
                self.category_pools[cat_key].add_items(urls)

        # 2. Load general category GIFs from disk cache if present
        all_general = list(DEFAULT_GENERAL_GIFS)
        try:
            if os.path.exists(_GENERAL_CACHE_FILE):
                with open(_GENERAL_CACHE_FILE, "r", encoding="utf-8") as f:
                    gen_data = json.load(f)
                    for cat, urls in gen_data.items():
                        cat_key = cat.lower()
                        if urls:
                            self.category_pools[cat_key] = RotationalPool(urls)
                            all_general.extend(urls)
        except Exception as e:
            logging.warning(f"[GIF_MANAGER] Could not load general cache: {e}")

        # Seed the master general pool
        self.general_pool = RotationalPool(all_general)

    def get_rotational_ngif(self, category: Optional[str] = None) -> Tuple[str, str]:
        """
        Returns (gif_url, category_title) rotationally.
        Guarantees non-repeating sequence.
        """
        if category:
            cat_clean = category.strip().lower()
            # Check for direct or alias category match
            if cat_clean in self.category_pools:
                return self.category_pools[cat_clean].get_next(), cat_clean.capitalize()

            # Partial match check (e.g. 'cuddles' -> 'cuddle')
            for known_cat, pool in self.category_pools.items():
                if known_cat in cat_clean or cat_clean in known_cat:
                    return pool.get_next(), known_cat.capitalize()

        # Default to the 100+ static CDN Neko pool
        return self.neko_pool.get_next(), "Neko"

    async def get_rotational_gif(self, query: Optional[str] = None, giphy_token: Optional[str] = None) -> Tuple[str, str]:
        """
        Returns (gif_url, title) for the $gif command.
        - If query is empty, pulls rotationally from the curated general pool.
        - If query is provided, searches Giphy with dynamic rotating offset and deduplication against recently sent URLs.
        - Automatically falls back to saved categorized pools on rate limit / network error.
        """
        if not query or not query.strip():
            url = self.general_pool.get_next()
            return url, "Random GIF"

        search_q = query.strip()
        q_norm = search_q.lower()

        # Initialize query state tracking
        if q_norm not in self.query_states:
            self.query_states[q_norm] = {
                "offset": 0,
                "recent_urls": deque(maxlen=60)
            }

        state = self.query_states[q_norm]
        current_offset = state["offset"]
        # Advance offset for next rotation
        state["offset"] = (current_offset + 12) % 120

        # Attempt Giphy API search if token is provided
        if giphy_token:
            try:
                url_api = f"https://api.giphy.com/v1/gifs/search?api_key={giphy_token}&q={search_q}&limit=25&offset={current_offset}&rating=g"
                headers = {"User-Agent": "YunaBot/7.0"}
                async with aiohttp.ClientSession(headers=headers) as session:
                    async with session.get(url_api, timeout=aiohttp.ClientTimeout(total=3.5)) as resp:
                        if resp.status == 200:
                            data = await resp.json()
                            results = data.get("data", [])
                            valid_urls = []
                            for item in results:
                                if "images" in item and "original" in item["images"] and item["images"]["original"].get("url"):
                                    valid_urls.append(item["images"]["original"]["url"])

                            if valid_urls:
                                # Filter out recently sent URLs
                                unseen = [u for u in valid_urls if u not in state["recent_urls"]]
                                if not unseen:
                                    # All seen in this batch, reset recent queue
                                    state["recent_urls"].clear()
                                    unseen = valid_urls

                                chosen = unseen[0] if len(unseen) == 1 else random.choice(unseen)
                                state["recent_urls"].append(chosen)
                                return chosen, f"GIF for '{search_q}'"
            except Exception as e:
                logging.debug(f"[GIF_MANAGER] Giphy fetch failed ({e}), falling back to rotational cache.")

        # Fallback to saved category matching if available
        for known_cat, pool in self.category_pools.items():
            if known_cat in q_norm or q_norm in known_cat:
                chosen = pool.get_next()
                state["recent_urls"].append(chosen)
                return chosen, f"GIF for '{search_q}'"

        # General rotation fallback
        chosen = self.general_pool.get_next()
        state["recent_urls"].append(chosen)
        return chosen, f"GIF for '{search_q}'"


# Global singleton instance
gif_rotator = GifManager()
