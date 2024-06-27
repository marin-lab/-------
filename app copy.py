import streamlit as st
import requests
from bs4 import BeautifulSoup
from retry import retry
import time
import numpy as np
import pandas as pd
import urllib

st.title('SUUMOスクレイピング')

# 文京区の町名リスト
towns = [
    "大塚", "音羽", "春日", "小石川", "後楽", "小日向", "水道", "関口", "千石",
    "千駄木", "西片", "根津", "白山", "本駒込", "本郷", "向丘", "目白台", "弥生", "湯島"
]

# 町名と対応するozパラメータの値
towns_dict = {town: f"131050{index+1:02}" for index, town in enumerate(towns)}

# ユーザーにオプションを選択してもらう
selected_towns = st.multiselect('町名（複数選択可）', towns)
selected_oz = [towns_dict[town] for town in selected_towns]

cb = st.number_input('最低価格（万円）', min_value=1.0, max_value=100.0, value=8.0)
ct = st.number_input('最高価格（万円）', min_value=1.0, max_value=100.0, value=11.0)
et = st.number_input('駅からの徒歩時間（分）', min_value=1, max_value=30, value=10)
cn = st.number_input('築年数（年）', min_value=0, max_value=100, value=20)  # 0 for new

# 最大ページ数の入力
max_page = st.number_input('スクレイピングする最大ページ数を入力してください', min_value=1, value=50)
st.caption('このままでも完了できますが、検索結果の画面のページ数をピッタリ入力すると早く終わります。検索条件の広さに合わせて修正してください。本来のページ数より少ないと途中でスクレイピングが終わってしまい、本来のページより多いとその分時間が長くなります。キリの良い数字で終わった時は少なすぎるかも')

# スクレイピング開始ボタン
start_button = st.button('開始')

# URLの動的生成
def generate_url(selected_oz, cb, ct, et, cn, page):
    base_url = 'https://suumo.jp/jj/chintai/ichiran/FR301FC001/?'
    params = {
        'ar': '030',
        'bs': '040',
        'pc': '30',
        'smk': '',
        'po1': '25',
        'po2': '99',
        'shkr1': '03',
        'shkr2': '03',
        'shkr3': '03',
        'shkr4': '03',
        'sc': '13105',
        'ta': '13',
        'cb': cb,
        'ct': ct,
        'et': et,
        'mb': '0',
        'mt': '9999999',
        'cn': cn,
        'fw2': '',
        'page': page
    }
    # Add multiple oz parameters
    oz_params = '&'.join([f'oz={oz}' for oz in selected_oz])
    return base_url + '&'.join([f'{key}={value}' for key, value in params.items()]) + '&' + oz_params

def get_total_properties_count(soup):
    count_element = soup.find('div', class_='paginate_set-hit')
    if count_element:
        count_text = count_element.get_text(strip=True)
        count = int(''.join(filter(str.isdigit, count_text.split('件')[0])))
        return count
    return 0

if start_button:
    data_samples = []
    times = []
    total_suumo_properties = 0  # SUUMOでの表示件数

    @retry(tries=3, delay=10, backoff=2)
    def load_page(url):
        html = requests.get(url)
        soup = BeautifulSoup(html.content, 'html.parser')
        return soup

    start = time.time()
    progress_bar = st.progress(0)
    status_text = st.empty()

    for page in range(1, max_page+1):
        before = time.time()
        url = generate_url(selected_oz, cb, ct, et, cn, page)
        soup = load_page(url)

        if page == 1:
            total_suumo_properties = get_total_properties_count(soup)

        mother = soup.find_all(class_='cassetteitem')

        for child in mother:
            data_home = []
            data_home.append(child.find(class_='ui-pct ui-pct--util1').text)
            data_home.append(child.find(class_='cassetteitem_content-title').text)
            data_home.append(child.find(class_='cassetteitem_detail-col1').text)
            children = child.find(class_='cassetteitem_detail-col2')
            for id, grandchild in enumerate(children.find_all(class_='cassetteitem_detail-text')):
                data_home.append(grandchild.text)
            children = child.find(class_='cassetteitem_detail-col3')
            for grandchild in children.find_all('div'):
                data_home.append(grandchild.text)

            rooms = child.find(class_='cassetteitem_other')
            for room in rooms.find_all(class_='js-cassette_link'):
                data_room = []
                for id_, grandchild in enumerate(room.find_all('td')):
                    if id_ == 2:
                        data_room.append(grandchild.text.strip())
                    elif id_ == 3:
                        data_room.append(grandchild.find(class_='cassetteitem_other-emphasis ui-text--bold').text)
                        data_room.append(grandchild.find(class_='cassetteitem_price cassetteitem_price--administration').text)
                    elif id_ == 4:
                        data_room.append(grandchild.find(class_='cassetteitem_price cassetteitem_price--deposit').text)
                        data_room.append(grandchild.find(class_='cassetteitem_price cassetteitem_price--gratuity').text)
                    elif id_ == 5:
                        data_room.append(grandchild.find(class_='cassetteitem_madori').text)
                        data_room.append(grandchild.find(class_='cassetteitem_menseki').text)
                    elif id_ == 8:
                        get_url = grandchild.find(class_='js-cassette_link_href cassetteitem_other-linktext').get('href')
                        abs_url = urllib.parse.urljoin(url, get_url)
                        data_room.append(abs_url)
                data_sample = data_home + data_room
                data_samples.append(data_sample)

        time.sleep(1)
        after = time.time()
        running_time = after - before
        times.append(running_time)
        running_mean = np.mean(times)
        running_required_time = running_mean * (max_page - page)
        hour = int(running_required_time / 3600)
        minute = int((running_required_time % 3600) / 60)
        second = int(running_required_time % 60)
        progress = page / max_page
        progress_bar.progress(progress)
        status_text.caption(f'総取得件数：{len(data_samples)}  残り時間：{hour}時間{minute}分{second}秒\n')

    status_text.caption('スクレイピング完了')
    st.write('表の右上から表をダウンロードしたり、一番上の1〜14を押して表を並べ替えたりできます。')
    st.write('全ての部屋情報')
    df = pd.DataFrame(data_samples)
    st.dataframe(df)

    st.write('重複物件に色を塗ったリスト')
    duplicated_mask = df.duplicated(subset=[0, 2] + list(range(6, 15)), keep=False)
    def highlight_duplicates(row):
        return ['background-color: yellow' if duplicated_mask[row.name] else '' for _ in row]
    styled_df = df.style.apply(highlight_duplicates, axis=1)
    num_duplicates = df[duplicated_mask].shape[0]
    unique_df = df.drop_duplicates(subset=[0, 2] + list(range(6, 15)))
    num_unique = unique_df.shape[0]
    total_properties = len(data_samples)
    duplicate_sets = df[df.duplicated(subset=[0, 2] + list(range(6, 15)), keep='first')]
    unique_count_with_duplicates = df.drop_duplicates(subset=[0, 2] + list(range(6, 15))).shape[0]
    st.dataframe(styled_df)
    st.divider()
    st.header(f'SUUMOでの表示物件数: {total_suumo_properties}')
    st.divider()
    st.header(f'収集できた全物件数: {total_properties}')
    st.divider()
    st.header(f'重複物件の数: {num_duplicates}')
    st.divider()
    st.header(f'重複を取り除いた本来の物件数: {unique_count_with_duplicates}')
