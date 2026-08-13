import requests
URL = "https://script.google.com/macros/s/AKfycbw_ARXW6wdw5ty4owuQWYQrPDh6ZcyH9p6NWBDG67834H474DAeKbkEmt6o_QPV75gg/exec"
requests.post(URL, json={"rows": [{
    "data": "2026-08-16", "pais": "brazil2", "mandante": "Operario PR",
    "horario": "12:00", "visitante": "Avai", "metodos": "TESTE-DIAG"
}]}, allow_redirects=False, timeout=30)