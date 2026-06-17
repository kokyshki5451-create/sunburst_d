import sqlite3
import pandas as pd
import plotly.express as px


def initialize_database():
    """Создает бд из скрипта db.sql"""
    try:
        # кннект к базе
        conn = sqlite3.connect('engineering_hierarchy.db')
        cursor = conn.cursor()

        # Проверка развертки таблиц
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
        existing_tables = [table[0] for table in cursor.fetchall()]

        # создание если ошибка
        if not existing_tables:
            print("Создаем базу данных...")
            with open('test1234.sql', 'r', encoding='utf-8') as f:
                sql_script = f.read()

            # Выполняем скрипт построчно для лучшего контроля
            for statement in sql_script.split(';'):
                if statement.strip():
                    try:
                        cursor.execute(statement)
                    except sqlite3.OperationalError as e:
                        print(f"Пропускаем ошибку в: {statement[:50]}... | Ошибка: {e}")

            conn.commit()
            print("База данных успешно инициализирована!")

            # проверка развертки созданных таблиц
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
            print("Созданные таблицы:", cursor.fetchall())
        else:
            print("База данных уже существует.")

        return conn

    except Exception as e:
        print("Ошибка при инициализации БД:", e)
        raise


def create_sunburst(conn):
    """Сама sunburst-диаграмма на основе данных из БД"""
    try:
        # Проверка
        cursor = conn.cursor()
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
        available_tables = [table[0] for table in cursor.fetchall()]
        print("Доступные таблицы:", available_tables)

        # иерархия
        if 'system' in available_tables:
            query = """
            SELECT 
                d.div_name AS division,
                p.pd_name AS pd,
                r.rd_name AS rd,
                s.system_name AS system
            FROM system s
            JOIN division d ON s.div_id = d.div_id
            JOIN pd p ON s.pd_id = p.pd_id
            JOIN rd r ON s.rd_id = r.rd_id
            """
            path = ['division', 'pd', 'rd', 'system']
        else:
            # упрощённая иерархия, если таблицы system нет
            query = """
            SELECT 
                d.div_name AS division,
                p.pd_name AS pd,
                r.rd_name AS rd
            FROM rd r
            JOIN pd p ON r.pd_name = p.pd_name
            JOIN division d ON p.div_id = d.div_id
            """
            path = ['division', 'pd', 'rd']

        df = pd.read_sql_query(query, conn)

        if df.empty:
            raise ValueError("Нет данных для построения диаграммы")

        fig = px.sunburst(
            df,
            path=path,
            title='Иерархия инженерных систем: ' + ' → '.join(path),
            width=1600,
            height=1600,
            color_discrete_sequence=px.colors.qualitative.Pastel
        )

        fig.update_traces(
            textinfo="label",
            insidetextorientation='radial',
            textfont_size=20,
            textfont=dict(family="Arial, sans-serif")
        )

        # ----- НОВЫЙ КОД ДЛЯ СОХРАНЕНИЯ HTML -----
        fig.write_html("sunburst.html")
        print("Диаграмма сохранена в sunburst.html")
        # -----------------------------------------

       

    except Exception as e:
        print("Ошибка при построении диаграммы:", e)
        raise


# скрипт санберста
if __name__ == "__main__":
    conn = None
    try:
        conn = initialize_database()
        create_sunburst(conn)
    finally:
        if conn:
            conn.close()
