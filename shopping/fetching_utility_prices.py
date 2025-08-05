import httpx
from bs4 import BeautifulSoup
import re


async def fetch_electricity_price():
    url = "https://euenergy.live/electricity-prices/bulgaria/sofia"
    async with httpx.AsyncClient() as client:
        response = await client.get(url)
        soup = BeautifulSoup(response.text, 'html.parser')

        subline_paragraphs = soup.find_all('p', class_='subline')

        if subline_paragraphs:
            spans = subline_paragraphs[0].find_all('span')
            if len(spans) >= 2:
                price_kwh = spans[1].text.strip()
                price_kwh = price_kwh.replace('€ ', '')
                return round(float(price_kwh) * 1.95583, 2)
    return None


async def fetch_cold_water():
    url = "https://www.sofiyskavoda.bg/en/water-tariff"
    async with httpx.AsyncClient() as client:
        response = await client.get(url)
        soup = BeautifulSoup(response.text, 'html.parser')

        td_blocks = soup.find_all('td', class_='table-header-block')
        for td in td_blocks:
            if "Total (supply, sewerage, treatment)" in td.text:

                td_with_price = td.find_next_sibling('td').find_next_sibling('td')
                if td_with_price:
                    divs = td_with_price.find_all('div')
                    for div in divs:
                        try:
                            price = round(float(div.text.strip()), 2)
                            return price
                        except ValueError:
                            continue
    return None


async def get_heating_price():
    url = "https://toplo.bg/prices"
    async with httpx.AsyncClient() as client:
        response = await client.get(url)
        soup = BeautifulSoup(response.text, 'html.parser')

        price_tags = soup.find_all('p', class_='red-text red-text-price')

        for tag in price_tags:
            match = re.search(r'(\d{2,3}[.,]\d{2})\s*лева', tag.text)
            if match:
                return float(match.group(1).replace(',', '.'))

    return None