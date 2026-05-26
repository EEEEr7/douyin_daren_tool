from __future__ import annotations

from datetime import datetime
from pathlib import Path

from openpyxl import Workbook

import config
from scraper.daily_quota import session_label_cn
from scraper.daren_profile import DarenContact

HEADERS = ["达人昵称", "微信号"]


def _contact_to_row(contact: DarenContact) -> list:
    return [contact.name, contact.wechat or ""]


def run_output_dir(session_label: str = "") -> Path:
    period = session_label_cn(session_label or "auto")
    folder_name = f"{config.APP_BRAND}_{datetime.now().strftime('%Y%m%d_%H%M')}_{period}"
    folder = config.OUTPUT_DIR / folder_name
    folder.mkdir(parents=True, exist_ok=True)
    return folder


def export_to_excel(contacts: list[DarenContact], *, session_label: str = "") -> Path:
    output_dir = run_output_dir(session_label)
    output_path = output_dir / config.EXCEL_FILENAME

    workbook = Workbook()
    sheet = workbook.active
    sheet.title = config.EXCEL_SHEET_NAME
    sheet.append(HEADERS)

    for contact in contacts:
        if not contact.wechat:
            continue
        sheet.append(_contact_to_row(contact))

    for column in sheet.columns:
        max_length = 0
        column_letter = column[0].column_letter
        for cell in column:
            if cell.value:
                max_length = max(max_length, len(str(cell.value)))
        sheet.column_dimensions[column_letter].width = min(max_length + 2, 60)

    workbook.save(output_path)
    return output_path
