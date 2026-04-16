import requests
import json
import os
from datetime import datetime

ACCESS_TOKEN = os.environ['IG_ACCESS_TOKEN']
INSTAGRAM_ACCOUNT_ID = os.environ['IG_ACCOUNT_ID']
JSON_FILE = 'insta_stats.json'

def get_followers_count():
    url = f"https://graph.facebook.com/v22.0/{INSTAGRAM_ACCOUNT_ID}"
    res = requests.get(url, params={
        'access_token': ACCESS_TOKEN,
        'fields': 'followers_count'
    }).json()
    if 'error' in res:
        print(f"Warning: Could not fetch followers_count: {res['error'].get('message', 'unknown error')}")
        return None
    return res.get('followers_count')

def get_reels_data():
    # 1. 投稿一覧を取得（media_product_typeでリールを判別するためフィールドに追加）
    media_url = f"https://graph.facebook.com/v22.0/{INSTAGRAM_ACCOUNT_ID}/media"
    res = requests.get(media_url, params={
        'access_token': ACCESS_TOKEN,
        'fields': 'id,caption,media_type,media_product_type,timestamp'
    }).json()

    today = datetime.now().strftime('%Y-%m-%d')
    new_stats = {}

    for media in res.get('data', []):
        # media_type が VIDEO または REEL、かつ media_product_type が REELS のものを対象にする
        is_reel = (
            media['media_type'] in ('VIDEO', 'REEL') and
            media.get('media_product_type') == 'REELS'
        )
        if not is_reel:
            continue

        m_id = media['id']
        # 2. インサイト取得
        ins_url = f"https://graph.facebook.com/v22.0/{m_id}/insights"
        # views: 再生数(v22.0以降はplaysの代替), reach: リーチ, saved: 保存数, total_interactions: いいね+保存+コメント+シェアの合計
        ins_params = {
            'metric': 'views,reach,saved,total_interactions,likes,comments,shares',
            'period': 'lifetime',
            'access_token': ACCESS_TOKEN
        }
        ins_res = requests.get(ins_url, params=ins_params).json()

        # 数値のパース
        metrics = {'date': today}
        if 'data' in ins_res:
            for m in ins_res['data']:
                # ライフタイムメトリクスは values 配列か直接 value フィールドで返る
                if 'values' in m and len(m['values']) > 0:
                    metrics[m['name']] = m['values'][0]['value']
                elif 'value' in m:
                    metrics[m['name']] = m['value']
        else:
            print(f"Warning: No data for {m_id}: {ins_res.get('error', {}).get('message', 'unknown error')}")

        new_stats[m_id] = {
            'caption': media.get('caption', '')[:30],
            'created_at': media['timestamp'],
            'metrics': metrics
        }
    return new_stats

def update_json():
    # 既存データの読み込み
    if os.path.exists(JSON_FILE):
        with open(JSON_FILE, 'r', encoding='utf-8') as f:
            full_data = json.load(f)
    else:
        full_data = {}

    # フォロワー数の取得・蓄積
    today = datetime.now().strftime('%Y-%m-%d')
    followers = get_followers_count()
    if followers is not None:
        if 'follower_history' not in full_data:
            full_data['follower_history'] = []
        if not any(h['date'] == today for h in full_data['follower_history']):
            full_data['follower_history'].append({'date': today, 'followers_count': followers})

    # 最新データの取得
    latest_reels = get_reels_data()

    # データの統合
    for m_id, info in latest_reels.items():
        if m_id not in full_data:
            full_data[m_id] = {
                'caption': info['caption'],
                'created_at': info['created_at'],
                'history': []
            }
        # 今日のデータがまだ無ければ追加（重複防止）
        if not any(h['date'] == info['metrics']['date'] for h in full_data[m_id]['history']):
            full_data[m_id]['history'].append(info['metrics'])

    # 保存
    with open(JSON_FILE, 'w', encoding='utf-8') as f:
        json.dump(full_data, f, ensure_ascii=False, indent=2)
    print(f"Updated: {len(latest_reels)} reels saved to {JSON_FILE}")

if __name__ == "__main__":
    update_json()