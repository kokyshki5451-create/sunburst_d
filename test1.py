import sqlite3
import pandas as pd
import plotly.express as px
import tkinter as tk
from tkinter import ttk, messagebox
import os

DB_NAME = 'engineering_hierarchy.db'
SQL_FILE = r'C:\Users\Lenovo\Documents\test1234.sql' # Убедитесь, что путь верный

def init_database():
    """Инициализирует БД: создает основные таблицы и справочники КИСУП, если их нет."""
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    
    # 1. Проверяем, есть ли уже таблица rd (признак того, что основная БД развернута)
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='rd';")
    if not cursor.fetchone():
        print("Основная БД не найдена. Пытаемся загрузить из test1234.sql...")
        if os.path.exists(SQL_FILE):
            with open(SQL_FILE, 'r', encoding='utf-8') as f:
                sql_script = f.read()
            cursor.executescript(sql_script)
            conn.commit()
            print("Основная БД успешно создана из файла.")
        else:
            messagebox.showerror("Ошибка", f"Файл {SQL_FILE} не найден!")
            return None

    # 2. Создаем таблицы справочника КИСУП, если их еще нет
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='object_type';")
    if not cursor.fetchone():
        print("Создаем справочники КИСУП...")
        cursor.executescript("""
            CREATE TABLE "object_type" (
                "type_id" INTEGER NOT NULL UNIQUE,
                "industry" TEXT NOT NULL,
                "purpose" TEXT NOT NULL,
                "type_name" TEXT NOT NULL,
                PRIMARY KEY("type_id")
            );
            CREATE TABLE "rd_budget_share" (
                "type_id" INTEGER NOT NULL,
                "rd_id" INTEGER NOT NULL,
                "budget_share" REAL NOT NULL,
                PRIMARY KEY("type_id", "rd_id"),
                FOREIGN KEY("type_id") REFERENCES "object_type"("type_id"),
                FOREIGN KEY("rd_id") REFERENCES "rd"("rd_id")
            );
        """)
        
        # Вставка репрезентативных данных (выборка ключевых объектов из разных отраслей)
        objects_data = [
            (10101, 'Транспортная инфраструктура', 'Вокзал ж/д', 'Вокзал ж/д'),
            (10302, 'Транспортная инфраструктура', 'Аэропорт', 'Аэровокзальный комплекс'),
            (30101, 'Торговые сети и коммерческая недвижимость', 'Торговые сети', 'Премиум-сегмент'),
            (30301, 'Торговые сети и коммерческая недвижимость', 'Бизнес-центр', 'Класс A (наивысший)'),
            (40101, 'Социальная инфраструктура', 'ЖК', 'Эконом-класс'),
            (40301, 'Социальная инфраструктура', 'СОШ', 'Муниципальный'),
            (60101, 'Промышленность', 'Судостроительный завод', 'Судостроительный/судоремонтный завод'),
            (70101, 'Телекоммуникации и IT-инфраструктура', 'ЦОД', 'Tier I - базовая инфраструктура'),
            (80101, 'Медицинские объекты', 'Поликлиника', 'Поликлиника'),
            (90101, 'Спортивные объекты', 'Стадион', 'Открытая арена')
        ]
        cursor.executemany("INSERT INTO object_type VALUES (?, ?, ?, ?)", objects_data)

        # Пример данных долей бюджета (rd_id маппится на ИСС из справочника)
        # rd_id: 1=ЭС, 2=ЭН, 3=ЭМ, 4=ЭО, 5=ЭГ, 7=АУПТ, 8=ВК(наруж), 9=ВК(внутр), 10=ОВ, 11=ИТП, 13=СКС, 16=АК, 17=ВН, 18=ОС, 19=СКУД, 20=ТО, 25=АПС
        shares_data = [
            # type_id 40101 (ЖК Эконом)
            (40101, 9, 1.10), (40101, 10, 0.55), (40101, 3, 2.40), (40101, 4, 0.30), (40101, 5, 1.80), (40101, 16, 1.05),
            # type_id 70101 (ЦОД Tier I)
            (70101, 9, 1.80), (70101, 10, 0.60), (70101, 3, 2.50), (70101, 4, 0.25), (70101, 5, 1.80), (70101, 2, 0.80), (70101, 19, 1.10),
            # type_id 30301 (Бизнес-центр А)
            (30301, 9, 1.30), (30301, 10, 0.60), (30301, 3, 2.50), (30301, 4, 0.40), (30301, 5, 2.00), (30301, 13, 0.60),
            # type_id 80101 (Поликлиника)
            (80101, 9, 1.20), (80101, 10, 0.60), (80101, 3, 2.45), (80101, 4, 0.35), (80101, 5, 1.90), (80101, 16, 1.10), (80101, 25, 0.10),
            # type_id 90101 (Стадион)
            (90101, 9, 0.50), (90101, 10, 0.70), (90101, 3, 2.40), (90101, 4, 1.10), (90101, 5, 1.50), (90101, 16, 0.80)
        ]
        cursor.executemany("INSERT INTO rd_budget_share VALUES (?, ?, ?)", shares_data)
        conn.commit()
        print("Справочники КИСУП успешно инициализированы.")
        
    return conn

class App:
    def __init__(self, root, conn):
        self.root = root
        self.conn = conn
        self.root.title("Анализ бюджета ИСС по типам объектов (КИСУП)")
        self.root.geometry("600x300")
        self.root.configure(padx=20, pady=20)

        # Загрузка отраслей
        self.industries = self.get_industries()
        
        # UI Элементы
        tk.Label(root, text="Выберите отрасль:", font=("Arial", 12)).grid(row=0, column=0, sticky="w", pady=10)
        self.cb_industry = ttk.Combobox(root, values=self.industries, state="readonly", width=50, font=("Arial", 11))
        self.cb_industry.grid(row=0, column=1, pady=10)
        self.cb_industry.bind("<<ComboboxSelected>>", self.on_industry_change)

        tk.Label(root, text="Выберите тип объекта:", font=("Arial", 12)).grid(row=1, column=0, sticky="w", pady=10)
        self.cb_object = ttk.Combobox(root, state="readonly", width=50, font=("Arial", 11))
        self.cb_object.grid(row=1, column=1, pady=10)

        self.btn_plot = tk.Button(root, text="Построить диаграмму", command=self.generate_chart, 
                                  bg="#4CAF50", fg="white", font=("Arial", 12, "bold"), padx=10, pady=5)
        self.btn_plot.grid(row=2, column=0, columnspan=2, pady=30)

    def get_industries(self):
        query = "SELECT DISTINCT industry FROM object_type ORDER BY industry;"
        df = pd.read_sql_query(query, self.conn)
        return df['industry'].tolist()

    def on_industry_change(self, event):
        selected_industry = self.cb_industry.get()
        query = "SELECT type_name FROM object_type WHERE industry = ? ORDER BY type_name;"
        df = pd.read_sql_query(query, self.conn, params=(selected_industry,))
        self.cb_object['values'] = df['type_name'].tolist()
        self.cb_object.set('') # Сброс выбора

    def generate_chart(self):
        selected_type = self.cb_object.get()
        if not selected_type:
            messagebox.showwarning("Предупреждение", "Пожалуйста, выберите тип объекта!")
            return

        # SQL-запрос: агрегируем долю бюджета по Разделам ПД (rd) для выбранного типа объекта
        query = """
            SELECT 
                ot.type_name AS "Тип объекта",
                r.rd_pref || ' - ' || r.rd_name AS "Раздел ПД",
                SUM(rbs.budget_share) AS "Доля бюджета (%)"
            FROM rd_budget_share rbs
            JOIN rd r ON rbs.rd_id = r.rd_id
            JOIN object_type ot ON rbs.type_id = ot.type_id
            WHERE ot.type_name = ?
            GROUP BY ot.type_name, r.rd_pref, r.rd_name
            ORDER BY "Доля бюджета (%)" DESC
        """
        
        try:
            df = pd.read_sql_query(query, self.conn, params=(selected_type,))
            
            if df.empty or df["Доля бюджета (%)"].sum() == 0:
                messagebox.showinfo("Информация", f"Для объекта '{selected_type}' нет данных о долях бюджета в справочнике.")
                return

            # Построение Sunburst диаграммы
            fig = px.sunburst(
                df,
                path=["Тип объекта", "Раздел ПД"],
                values="Доля бюджета (%)",
                title=f"Структура бюджета ИСС: {selected_type}\n(Размеры секторов пропорциональны доле в бюджете)",
                color="Доля бюджета (%)",
                color_continuous_scale="Viridis",
                hover_data={"Доля бюджета (%)": ":.2f"} # Форматирование при наведении
            )

            # Настройка внешнего вида
            fig.update_traces(
                textinfo="label+percent entry",
                insidetextorientation='radial',
                textfont_size=14,
                marker=dict(line=dict(width=2, color='white'))
            )
            
            fig.update_layout(
                margin=dict(t=50, l=0, r=0, b=0),
                font=dict(family="Arial, sans-serif")
            )

            # Открываем диаграмму в браузере
            fig.show()

        except Exception as e:
            messagebox.showerror("Ошибка", f"Не удалось построить диаграмму:\n{e}")

if __name__ == "__main__":
    # Инициализация БД
    connection = init_database()
    
    if connection:
        # Запуск GUI приложения
        root = tk.Tk()
        app = App(root, connection)
        
        # Обработчик закрытия окна для корректного завершения соединения с БД
        root.protocol("WM_DELETE_WINDOW", lambda: (connection.close(), root.destroy()))
        
        root.mainloop()
