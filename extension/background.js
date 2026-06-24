// 右鍵選單:選取文字 → 到 TamonRadar 搜尋
const SITE = "https://tamonradar.snowrealm.pet"; // 換成你的前端網址(或在 popup 設定)

chrome.runtime.onInstalled.addListener(() => {
  chrome.contextMenus.create({
    id: "tamonradar-search",
    title: "用 TamonRadar 搜尋「%s」",
    contexts: ["selection"],
  });
});

chrome.contextMenus.onClicked.addListener(async (info) => {
  if (info.menuItemId !== "tamonradar-search" || !info.selectionText) return;
  const { site } = await chrome.storage.sync.get("site");
  const base = site || SITE;
  chrome.tabs.create({ url: `${base}/?q=${encodeURIComponent(info.selectionText)}` });
});
