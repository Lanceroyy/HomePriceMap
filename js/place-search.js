(function () {
  "use strict";

  const CATALOG_URL = "/data/place_index.json";
  let catalogPromise;

  function normalize(value) {
    return String(value || "")
      .normalize("NFD")
      .replace(/[\u0300-\u036f]/g, "")
      .toLowerCase()
      .replace(/[^a-z0-9]+/g, " ")
      .trim();
  }

  function labelFor(place) {
    return `${place.name}, ${place.state}`;
  }

  function searchableText(place) {
    return normalize(`${place.name} ${place.state} ${place.type} ${place.county || ""}`);
  }

  async function loadCatalog() {
    if (!catalogPromise) {
      catalogPromise = fetch(CATALOG_URL, { credentials: "same-origin" })
        .then((response) => {
          if (!response.ok) throw new Error(`Place catalog returned ${response.status}`);
          return response.json();
        })
        .then((payload) => {
          if (!payload || !Array.isArray(payload.places)) {
            throw new Error("Place catalog has an invalid format");
          }
          return payload.places.map((place) => ({
            ...place,
            _label: labelFor(place),
            _search: searchableText(place),
          }));
        })
        .catch((error) => {
          catalogPromise = null;
          throw error;
        });
    }
    return catalogPromise;
  }

  function score(place, query) {
    const name = normalize(place.name);
    const label = normalize(place._label);
    if (name === query) return 0;
    if (name.startsWith(query)) return 1;
    if (label.startsWith(query)) return 2;
    if (place._search.split(" ").some((word) => word.startsWith(query))) return 3;
    if (place._search.includes(query)) return 4;
    return Number.POSITIVE_INFINITY;
  }

  function findMatches(places, rawQuery, limit) {
    const query = normalize(rawQuery);
    if (query.length < 2) return [];
    return places
      .map((place) => ({ place, rank: score(place, query) }))
      .filter((item) => Number.isFinite(item.rank))
      .sort((a, b) =>
        a.rank - b.rank ||
        a.place.name.localeCompare(b.place.name) ||
        a.place.state.localeCompare(b.place.state) ||
        a.place.type.localeCompare(b.place.type)
      )
      .slice(0, limit)
      .map((item) => item.place);
  }

  function attach(input, results, options) {
    if (!input || !results) throw new Error("Place search requires an input and results list");
    const settings = Object.assign({ limit: 8, onSelect: null }, options || {});
    let matches = [];
    let activeIndex = -1;
    let requestNumber = 0;

    function setExpanded(expanded) {
      input.setAttribute("aria-expanded", expanded ? "true" : "false");
      results.hidden = !expanded;
      if (!expanded) {
        activeIndex = -1;
        input.removeAttribute("aria-activedescendant");
      }
    }

    function showStatus(message, className) {
      results.replaceChildren();
      const item = document.createElement("li");
      item.className = className || "place-search-status";
      item.setAttribute("role", "status");
      item.textContent = message;
      results.appendChild(item);
      setExpanded(true);
    }

    function setActive(index) {
      if (!matches.length) return;
      activeIndex = (index + matches.length) % matches.length;
      const optionsList = results.querySelectorAll('[role="option"]');
      optionsList.forEach((option, optionIndex) => {
        const selected = optionIndex === activeIndex;
        option.setAttribute("aria-selected", selected ? "true" : "false");
        option.classList.toggle("active", selected);
      });
      const active = optionsList[activeIndex];
      if (active) {
        input.setAttribute("aria-activedescendant", active.id);
        active.scrollIntoView({ block: "nearest" });
      }
    }

    function select(place) {
      input.value = place._label;
      setExpanded(false);
      if (typeof settings.onSelect === "function") settings.onSelect(place);
    }

    function render(nextMatches) {
      matches = nextMatches;
      activeIndex = -1;
      input.removeAttribute("aria-activedescendant");
      results.replaceChildren();
      if (!matches.length) {
        showStatus("No published city or county profiles match that search.", "place-search-status");
        return;
      }

      matches.forEach((place, index) => {
        const item = document.createElement("li");
        item.id = `${input.id}-option-${index}`;
        item.className = "place-search-option";
        item.setAttribute("role", "option");
        item.setAttribute("aria-selected", "false");

        const label = document.createElement("span");
        label.className = "place-search-label";
        label.textContent = place._label;
        const detail = document.createElement("span");
        detail.className = "place-search-detail";
        detail.textContent = place.type === "county"
          ? "County profile"
          : `${place.county ? `${place.county} · ` : ""}City profile`;
        item.append(label, detail);
        item.addEventListener("mousedown", (event) => event.preventDefault());
        item.addEventListener("click", () => select(place));
        results.appendChild(item);
      });
      setExpanded(true);
    }

    async function update() {
      const query = input.value.trim();
      const currentRequest = ++requestNumber;
      if (normalize(query).length < 2) {
        matches = [];
        setExpanded(false);
        return;
      }
      showStatus("Searching published profiles…", "place-search-status loading");
      try {
        const places = await loadCatalog();
        if (currentRequest !== requestNumber) return;
        render(findMatches(places, query, settings.limit));
      } catch (error) {
        if (currentRequest !== requestNumber) return;
        console.error("Failed to load place catalog", error);
        showStatus("Place search is temporarily unavailable. Please try again.", "place-search-status error");
      }
    }

    input.addEventListener("input", update);
    input.addEventListener("keydown", (event) => {
      if (event.key === "ArrowDown") {
        if (matches.length) {
          event.preventDefault();
          setActive(activeIndex + 1);
        }
      } else if (event.key === "ArrowUp") {
        if (matches.length) {
          event.preventDefault();
          setActive(activeIndex - 1);
        }
      } else if (event.key === "Enter") {
        if (activeIndex >= 0 && matches[activeIndex]) {
          event.preventDefault();
          select(matches[activeIndex]);
        }
      } else if (event.key === "Escape") {
        requestNumber += 1;
        matches = [];
        setExpanded(false);
      }
    });
    input.addEventListener("blur", () => window.setTimeout(() => setExpanded(false), 120));
    input.addEventListener("focus", () => {
      if (matches.length) setExpanded(true);
    });

    return { loadCatalog, update };
  }

  window.HomePriceSearch = { attach, findMatches, loadCatalog, normalize };
})();
