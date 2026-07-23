import sqlite3
import pandas as pd
import plotly.express as px
import os

DB_FILE = 'engineering_hierarchy.db'
SQL_FILE = 'test123.db.sql' # Берем файл прямо из репозитория

def init_db():
    """Инициализирует БД из файла скрипта, если её еще нет"""
    if not os.path.exists(DB_FILE):
        print(f"Создаем БД из {SQL_FILE}...")
        if not os.path.exists(SQL_FILE):
            raise FileNotFoundError(f"Файл {SQL_FILE} не найден в репозитории!")
        
        conn = sqlite3.connect(DB_FILE)
        with open(SQL_FILE, 'r', encoding='utf-8') as f:
            conn.executescript(f.read())
        conn.commit()
        print("✅ БД успешно создана.")
    else:
        print("ℹ️ БД уже существует.")
    
    return sqlite3.connect(DB_FILE)

def generate_html(conn):
    """Строит Sunburst и сохраняет его в index.html"""
    # Запрос объединяет Отрасль, Тип объекта и Раздел ПД, используя долю бюджета как размер сектора
    query = """
        SELECT 
            ot.industry AS "Отрасль",
            ot.type_name AS "Тип объекта",
            r.rd_pref || ' - ' || r.rd_name AS "Раздел ПД",
            rbs.budget_share AS "Доля бюджета (%)"
        FROM rd_budget_share rbs
        JOIN object_type ot ON rbs.type_id = ot.type_id
        JOIN rd r ON rbs.rd_id = r.rd_id
        WHERE rbs.budget_share > 0
        ORDER BY ot.industry, ot.type_name, rbs.budget_share DESC
    """
    
    df = pd.read_sql_query(query, conn)
    
    if df.empty:
        raise ValueError("Нет данных для построения диаграммы. Проверьте таблицы rd_budget_share и object_type.")

    print(f"📊 Найдено {len(df)} записей для построения диаграммы.")

    # Строим интерактивную Sunburst диаграмму
    fig = px.sunburst(
        df,
        path=["Отрасль", "Тип объекта", "Раздел ПД"],
        values="Доля бюджета (%)",
        title="Структура бюджета ИСС: Отрасль → Тип объекта → Раздел ПД",
        color="Доля бюджета (%)",
        color_continuous_scale="Viridis",
        hover_data={"Доля бюджета (%)": ":.2f"}
    )

    fig.update_traces(
        textinfo="label+percent entry",
        insidetextorientation='radial',
        textfont_size=12
    )
    
    fig.update_layout(
        margin=dict(t=60, l=0, r=0, b=0),
        width=1200,
        height=1200
    )

    # ГЛАВНОЕ ИСПРАВЛЕНИЕ: Сохраняем в файл, а не пытаемся открыть в браузере
    output_file = "index.html"
    fig.write_html(output_file)
    print(f"✅ Файл {output_file} успешно создан и готов к коммиту!")

if __name__ == "__main__":
    try:
        conn = init_db()
        generate_html(conn)
        conn.close()
    except Exception as e:
        print(f"❌ Критическая ошибка: {e}")
        raise  # Принудительно завершаем с ошибкой, чтобы GitHub Actions подсветил проблему
