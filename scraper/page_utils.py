from __future__ import annotations

from playwright.sync_api import Page

DISMISS_TEXTS = ("我知道了", "知道了", "确定", "继续使用", "关闭")


def dismiss_overlays(page: Page) -> None:
    page.evaluate(
        """
        () => {
            const root = document.getElementById('browser-blocker-plugin-root');
            if (root) root.remove();
            document.querySelectorAll('.browser-blocker-plugin-modal-wrap').forEach(el => el.remove());
        }
        """
    )

    for text in DISMISS_TEXTS:
        button = page.get_by_text(text, exact=True)
        if button.count() > 0:
            try:
                if button.first.is_visible():
                    button.first.click()
                    page.wait_for_timeout(500)
            except Exception:
                pass

    page.evaluate(
        """
        () => {
            document.querySelectorAll('.auxo-modal-wrap, .auxo-modal-mask').forEach(el => {
                if (el.textContent && el.textContent.includes('浏览器')) {
                    el.remove();
                }
            });
        }
        """
    )
