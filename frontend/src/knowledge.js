/**
 * Client-side mirror of the backend deep_merge.
 * Merges `updates` into `base` non-destructively — never overwrites with empties.
 */
export const knowledge = {
  deepMerge(base = {}, updates = {}) {
    const result = { ...base };
    for (const [key, value] of Object.entries(updates)) {
      if (value === null || value === "" || value === undefined) continue;
      if (typeof value === "object" && !Array.isArray(value) && Object.keys(value).length === 0) continue;
      if (typeof value === "object" && !Array.isArray(value) && typeof result[key] === "object") {
        result[key] = this.deepMerge(result[key], value);
      } else {
        result[key] = value;
      }
    }
    return result;
  },
};
