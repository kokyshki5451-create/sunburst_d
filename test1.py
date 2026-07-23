import sqlite3
import pandas as pd
import plotly.express as px
import os
import sys

DB_FILE = 'engineering_hierarchy.db'
SQL_FILE = 'test123.db.sql'

def log(msg):
    print(f"[{pd.Timestamp.now()}] {msg}", flush=True)

def initialize_database():
    """Создает БД из SQL-скрипта."""
    log(f"🔍 Проверяем файлы...")
    log(f"   Текущая директория: {os.getcwd()}")
    log(f"   Файлы в директории: {os.listdir('.')}")
    
    if not os.path.exists(SQL_FILE):
        raise FileNotFoundError(f"❌ Файл {SQL_FILE} не найден!")
    
    if os.path.exists(DB_FILE):
        os.remove(DB_FILE)
        log(f"🗑️ Удаляем старую БД")
    
    log(f"📦 Создаём БД из {SQL_FILE}...")
    conn = sqlite3.connect(DB_FILE)
    with open(SQL_FILE, 'r', encoding='utf-8') as f:
        sql_script = f.read()
    conn.executescript(sql_script)
    conn.commit()
    
    # Проверка таблиц
    cursor = conn.cursor()
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name;")
    tables = [row[0] for row in cursor.fetchall()]
    log(f"✅ Созданы таблицы: {tables}")
    
    # Проверка количества записей
    for table in ['object_type', 'rd_budget_share', 'rd', 'pd', 'division', 'system']:
        if table in tables:
            cursor.execute(f"SELECT COUNT(*) FROM {table}")
            count = cursor.fetchone()[0]
            log(f"   📊 {table}: {count} записей")
    
    return conn

def generate_html(conn):
    """Строит Sunburst и сохраняет в index.html."""
    log("📊 Строим запрос...")
    
    query = """
        SELECT 
            ot.industry AS "Отрасль",
            ot.type_name AS "Тип объекта",
            d.div_name AS "Division",
            p.pd_name AS "PD",
            r.rd_pref || ' - ' || r.rd_name AS "RD",
            s.system_name AS "System",
            ROUND(rbs.budget_share * 1.0 / 
                COUNT(s.system_id) OVER (PARTITION BY rbs.type_id, r.rd_id), 3
            ) AS "Доля бюджета (%)"
        FROM rd_budget_share rbs
        JOIN object_type ot ON rbs.type_id = ot.type_id
        JOIN rd r ON rbs.rd_id = r.rd_id
        JOIN pd p ON r.pd_name = p.pd_name
        JOIN division d ON p.div_id = d.div_id
        JOIN system s ON s.rd_id = r.rd_id
        WHERE rbs.budget_share > 0
        ORDER BY "Доля бюджета (%)" DESC
    """
    
    df = pd.read_sql_query(query, conn)
    log(f"✅ Получено {len(df)} записей")
    
    if df.empty:
        raise ValueError("Нет данных для построения диаграммы!")
    
    log("🎨 Строим Sunburst...")
    fig = px.sunburst(
        df,
        path=["Отрасль", "Тип объекта", "Division", "PD", "RD", "System"],
        values="Доля бюджета (%)",
        title="Полная иерархия ИСС: Структура бюджета по типам объектов",
        color="Доля бюджета (%)",
        color_continuous_scale="Viridis",
        hover_data={"Доля бюджета (%)": ":.3f"}
    )
    
    fig.update_traces(
        textinfo="label+percent entry",
        insidetextorientation='radial',
        textfont_size=12,
        marker=dict(line=dict(width=1.5, color='white'))
    )
    
    fig.update_layout(
        margin=dict(t=60, l=0, r=0, b=0),
        font=dict(family="Arial, sans-serif"),
        width=1400,
        height=1400
    )
    
    output_file = "index.html"
    fig.write_html(output_file)
    
    if not os.path.exists(output_file):
        raise RuntimeError("❌ Файл index.html не создан!")
    
    size = os.path.getsize(output_file)
    log(f"✅ Файл {output_file} создан! Размер: {size} байт")

if __name__ == "__main__":
    try:
        log("🚀 Запуск скрипта...")
        conn = initialize_database()
        generate_html(conn)
        conn.close()
        log("🎉 Успешно завершено!")
    except Exception as e:
        log(f"💥 КРИТИЧЕСКАЯ ОШИБКА: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
