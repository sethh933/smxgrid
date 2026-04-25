const DEFAULT_RIDER_PROFILE_BASE_URL = "https://smxmuse.com/rider";

const slugifyRiderName = (name) =>
  String(name || "")
    .normalize("NFKD")
    .replace(/[\u0300-\u036f]/g, "")
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, "-")
    .replace(/^-+|-+$/g, "");

export const buildRiderProfileUrl = (name, riderId) => {
  const slug = slugifyRiderName(name);

  if (!slug || riderId === undefined || riderId === null || riderId === "") {
    return "";
  }

  const baseUrl = (
    import.meta.env.VITE_SMXMUSE_RIDER_PROFILE_BASE_URL ||
    DEFAULT_RIDER_PROFILE_BASE_URL
  ).replace(/\/+$/, "");

  return `${baseUrl}/${slug}-${riderId}`;
};
