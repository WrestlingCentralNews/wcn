// Single place for Google AdSense settings. Set enabled:true and fill IDs after AdSense approval.
window.ADS_CONFIG = {
  enabled: false,
  publisherId: "ca-pub-6049350409363098",
  slots: { leaderboard: "", leftSkyscraper: "", rightSkyscraper: "",
           inFeed: "", footer: "", mobileSticky: "" },
  inFeedEvery: 4
};
// Google Analytics 4 measurement ID (reference only): gtag.js is now loaded directly in every page <head> via GA_HEAD in pages.py.
window.ANALYTICS_CONFIG = { measurementId: "G-VXM9BRSC0B" };
// While ads are off (before AdSense approval) the empty ad boxes are hidden (style.css html.noads), so no page shows dashed
// 'Advertisement' placeholders around thin space. Turning enabled:true brings the reserved boxes back automatically.
if (!window.ADS_CONFIG.enabled) document.documentElement.classList.add("noads");
