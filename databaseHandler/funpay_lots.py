import requests
from bs4 import BeautifulSoup

def set_funpay_lot_active(lot_id: int, active: bool, golden_key: str) -> bool:
    session = requests.Session()
    headers = {
        "user-agent": "Mozilla/5.0",
        "cookie": f"golden_key={golden_key}",
    }
    edit_url = f"https://funpay.com/lots/edit/{lot_id}/"
    resp = session.get(edit_url, headers=headers)
    if resp.status_code != 200:
        print(f"Не удалось получить форму редактирования лота {lot_id}")
        return False

    soup = BeautifulSoup(resp.text, "html.parser")
    form = soup.find("form")
    if not form:
        print("Форма редактирования лота не найдена")
        return False

    data = {}
    for input_ in form.find_all("input"):
        name = input_.get("name")
        if not name:
            continue
        if input_.get("type") == "checkbox":
            if name == "active":
                if active:
                    data[name] = "on"
            elif input_.has_attr("checked"):
                data[name] = "on"
        else:
            data[name] = input_.get("value", "")

    for textarea in form.find_all("textarea"):
        name = textarea.get("name")
        if name:
            data[name] = textarea.text

    for select in form.find_all("select"):
        name = select.get("name")
        if name:
            selected = select.find("option", selected=True)
            if selected:
                data[name] = selected["value"]
            else:
                data[name] = ""

    resp2 = session.post(edit_url, data=data, headers=headers)
    if resp2.status_code in (200, 302):
        print(f"Лот {lot_id} {'активирован' if active else 'деактивирован'} на FunPay")
        return True
    else:
        print(f"Ошибка: код {resp2.status_code}")
        return False