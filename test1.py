import sqlite3
import pandas as pd
import plotly.express as px
import random # Для генерации тестовых данных

DB_NAME = 'engineering_hierarchy.db'
SQL_FILE = 'test1234.sql'

def initialize_database():
    """Создает БД из скрипта и добавляет таблицу метрик, если её нет"""
    try:
        conn = sqlite3.connect(DB_NAME)
        cursor = conn.cursor()

        # 1. Проверяем, есть ли уже таблицы
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
        existing_tables = [table[0] for table in cursor.fetchall()]

        # 2. Если таблиц нет вообще, создаем структуру из файла
        if not existing_tables:
            print("Создаем основную структуру БД...")
            with open(SQL_FILE, 'r', encoding='utf-8') as f:
                sql_script = f.read()
            
            # Выполняем скрипт
            cursor.executescript(sql_script)
            conn.commit()
            print("Структура БД создана.")

        # 3. Проверяем, есть ли таблица метрик (наших новых данных)
        if 'metrics' not in existing_tables:
            print("Добавляем таблицу для аналитики (metrics)...")
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS metrics (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    system_id INTEGER NOT NULL,
                    budget REAL NOT NULL, -- Здесь может быть стоимость, вес, количество
                    FOREIGN KEY(system_id) REFERENCES system(system_id)
                )
            """)
            conn.commit()
            print("Таблица metrics создана.")
        else:
            print("Таблица metrics уже существует.")

        return conn

    except Exception as e:
        print("Ошибка при инициализации БД:", e)
        raise

def populate_test_metrics(conn):
    """
    Заполняет таблицу metrics тестовыми данными.
    В реальном проекте здесь будет загрузка из Excel/CSV.
    """
    cursor = conn.cursor()
    
    # Проверяем, пустая ли таблица
    cursor.execute("SELECT COUNT(*) FROM metrics")
    count = cursor.fetchone()[0]
    
    if count == 0:
        print("Заполняем таблицу метрик тестовыми данными (бюджеты)...")
        
        # Получаем все system_id
        cursor.execute("SELECT system_id FROM system")
        systems = [row[0] for row in cursor.fetchall()]
        
        data_to_insert = []
        for sys_id in systems:
            # Генерируем случайный "бюджет" от 100к до 5млн для примера
            # Чем больше число, тем больше сектор на диаграмме
            budget = random.uniform(100000, 5000000)
            data_to_insert.append((sys_id, round(budget, 2)))
            
        cursor.executemany("INSERT INTO metrics (system_id, budget) VALUES (?, ?)", data_to_insert)
        conn.commit()
        print(f"Добавлено {len(data_to_insert)} записей метрик.")
    else:
        print("Метрики уже заполнены.")

def create_sunburst(conn):
    """Строит Sunburst с учетом веса (бюджета)"""
    try:
        cursor = conn.cursor()
        
        # Проверка наличия данных
        cursor.execute("SELECT COUNT(*) FROM metrics")
        if cursor.fetchone()[0] == 0:
            print("Внимание: Таблица metrics пуста. Диаграмма будет некорректной.")
            return

        # SQL-запрос с JOIN к таблице metrics и SUM для агрегации
        query = """
        SELECT 
            d.div_name AS Отдел,
            p.pd_name AS Подразделение,
            r.rd_name AS Раздел,
            s.system_name AS Система,
            SUM(m.budget) AS Общий_Бюджет
        FROM system s
        JOIN division d ON s.div_id = d.div_id
        JOIN pd p ON s.pd_id = p.pd_id
        JOIN rd r ON s.rd_id = r.rd_id
        JOIN metrics m ON s.system_id = m.system_id
        GROUP BY d.div_name, p.pd_name, r.rd_name, s.system_name
        ORDER BY Общий_Бюджет DESC
        """
        
        df = pd.read_sql_query(query, conn)

        if df.empty:
            raise ValueError("Нет данных для построения диаграммы")

        print(f"Построение диаграммы для {len(df)} уникальных систем...")

        # Построение диаграммы
        fig = px.sunburst(
            df,
            path=['Отдел', 'Подразделение', 'Раздел', 'Система'], # Иерархия
            values='Общий_Бюджет', # ВАЖНО: Размер сектора зависит от этого столбца
            title='Анализ инженерных систем по бюджету (руб.)',
            width=1200,
            height=1200,
            color='Отдел', # Раскрашиваем по отделам для наглядности
            color_discrete_sequence=px.colors.qualitative.Pastel
        )

        # Настройка внешнего вида
        fig.update_traces(
            textinfo="label+percent entry", # Показываем имя и % от родительского круга
            insidetextorientation='radial',
            textfont_size=12,
            hovertemplate="<b>%{label}</b><br>Бюджет: %{value:,.0f} руб.<extra></extra>"
        )
        
        # Убираем лишние отступы
        fig.update_layout(margin=dict(t=50, l=0, r=0, b=0))

        # Сохранение
        fig.write_html("index.html")
        print("✅ Диаграмма успешно сохранена в index.html")
        
        # Показываем топ-5 самых дорогих систем
        print("\n🔥 Топ-5 самых затратных систем:")
        print(df.nlargest(5, 'Общий_Бюджет')[['Система', 'Общий_Бюджет']])

    except Exception as e:
        print("Ошибка при построении диаграммы:", e)
        raise

if __name__ == "__main__":
    conn = None
    try:
        # 1. Создаем/подключаем БД
        conn = initialize_database()
        
        # 2. Добавляем тестовые цифры (если их нет)
        populate_test_metrics(conn)
        
        # 3. Строим диаграмму
        create_sunburst(conn)
        
    finally:
        if conn:
            conn.close()
