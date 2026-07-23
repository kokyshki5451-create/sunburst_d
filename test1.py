import sqlite3
import pandas as pd
import plotly.express as px
import tkinter as tk
from tkinter import ttk, messagebox
import os

# Путь к файлу БД и SQL-скрипту
DB_NAME = 'engineering_hierarchy.db'
SQL_FILE = r'C:\Users\Lenovo\Documents\test123.db.sql'  # Укажите путь к test123.db.sql


def initialize_database():
    """Подключается к БД. Если её нет — создаёт из test123.db.sql."""
    db_exists = os.path.exists(DB_NAME)
    
    if not db_exists:
        print(f"БД '{DB_NAME}' не найдена. Создаём из {SQL_FILE}...")
        if not os.path.exists(SQL_FILE):
            raise FileNotFoundError(f"SQL-файл не найден: {SQL_FILE}")
        
        conn = sqlite3.connect(DB_NAME)
        with open(SQL_FILE, 'r', encoding='utf-8') as f:
            sql_script = f.read()
        conn.executescript(sql_script)
        conn.commit()
        print("✅ База данных успешно создана!")
    else:
        conn = sqlite3.connect(DB_NAME)
        print(f"✅ Подключено к существующей БД: {DB_NAME}")
    
    return conn


class SunburstApp:
    def __init__(self, root, conn):
        self.root = root
        self.conn = conn
        self.root.title("КИСУП: Доли разделов ПД по типам объектов")
        self.root.geometry("700x350")
        self.root.configure(padx=20, pady=20)

        # Загрузка отраслей
        self.industries = self._get_industries()
        if not self.industries:
            messagebox.showerror("Ошибка", "В БД нет данных об отраслях!")
            root.destroy()
            return

        # === UI ===
        tk.Label(root, text="🏭 Отрасль:", font=("Arial", 12, "bold")).grid(
            row=0, column=0, sticky="w", pady=10)
        self.cb_industry = ttk.Combobox(
            root, values=self.industries, state="readonly", width=50, font=("Arial", 11))
        self.cb_industry.grid(row=0, column=1, pady=10)
        self.cb_industry.bind("<<ComboboxSelected>>", self.on_industry_change)
        self.cb_industry.current(0)

        tk.Label(root, text="🏢 Тип объекта:", font=("Arial", 12, "bold")).grid(
            row=1, column=0, sticky="w", pady=10)
        self.cb_object = ttk.Combobox(
            root, state="readonly", width=50, font=("Arial", 11))
        self.cb_object.grid(row=1, column=1, pady=10)

        self.btn_plot = tk.Button(
            root, text="📊 Построить Sunburst-диаграмму",
            command=self.generate_chart,
            bg="#4CAF50", fg="white", font=("Arial", 12, "bold"),
            padx=15, pady=8)
        self.btn_plot.grid(row=2, column=0, columnspan=2, pady=25)

        # Инициализация списка типов объектов
        self.on_industry_change(None)

    def _get_industries(self):
        query = "SELECT DISTINCT industry FROM object_type ORDER BY industry;"
        df = pd.read_sql_query(query, self.conn)
        return df['industry'].tolist()

    def on_industry_change(self, event):
        """Обновляет список типов объектов при смене отрасли."""
        selected_industry = self.cb_industry.get()
        query = """
            SELECT DISTINCT type_name 
            FROM object_type 
            WHERE industry = ? 
            ORDER BY type_name;
        """
        df = pd.read_sql_query(query, self.conn, params=(selected_industry,))
        self.cb_object['values'] = df['type_name'].tolist()
        if df['type_name'].tolist():
            self.cb_object.current(0)

    def generate_chart(self):
        """Строит Sunburst-диаграмму для выбранного типа объекта."""
        selected_type = self.cb_object.get()
        if not selected_type:
            messagebox.showwarning("Предупреждение", "Выберите тип объекта!")
            return

        # SQL-запрос: агрегируем доли бюджета по разделам ПД
        query = """
            SELECT 
                ot.type_name AS "Тип объекта",
                ot.industry AS "Отрасль",
                r.rd_pref || ' — ' || r.rd_name AS "Раздел ПД",
                SUM(rbs.budget_share) AS "Доля бюджета (%)"
            FROM rd_budget_share rbs
            JOIN rd r ON rbs.rd_id = r.rd_id
            JOIN object_type ot ON rbs.type_id = ot.type_id
            WHERE ot.type_name = ? AND rbs.budget_share > 0
            GROUP BY r.rd_pref, r.rd_name
            ORDER BY "Доля бюджета (%)" DESC
        """

        try:
            df = pd.read_sql_query(query, self.conn, params=(selected_type,))

            if df.empty or df["Доля бюджета (%)"].sum() == 0:
                messagebox.showinfo(
                    "Информация",
                    f"Для объекта '{selected_type}' нет данных о долях бюджета.")
                return

            # === Sunburst-диаграмма ===
            fig = px.sunburst(
                df,
                path=["Тип объекта", "Раздел ПД"],
                values="Доля бюджета (%)",
                title=(
                    f"Структура бюджета ИСС: {selected_type}\n"
                    f"(Размер сектора = доля от общего бюджета)"
                ),
                color="Доля бюджета (%)",
                color_continuous_scale="Viridis",
                hover_data={
                    "Доля бюджета (%)": ":.2f",
                    "Отрасль": True
                }
            )

            fig.update_traces(
                textinfo="label+percent entry",
                insidetextorientation='radial',
                textfont_size=13,
                marker=dict(line=dict(width=2, color='white'))
            )

            fig.update_layout(
                margin=dict(t=60, l=0, r=0, b=0),
                font=dict(family="Arial, sans-serif"),
                height=800
            )

            fig.show()

            # === Таблица с детализацией ===
            print("\n" + "=" * 70)
            print(f"📋 Ранжирование разделов ПД по доле в бюджете: {selected_type}")
            print("=" * 70)
            print(df[["Раздел ПД", "Доля бюджета (%)"]].to_string(index=False))
            print(f"\n💰 ИТОГО доля ИСС: {df['Доля бюджета (%)'].sum():.2f}%")
            print("=" * 70)

        except Exception as e:
            messagebox.showerror("Ошибка", f"Не удалось построить диаграмму:\n{e}")


if __name__ == "__main__":
    conn = None
    try:
        conn = initialize_database()
        root = tk.Tk()
        app = SunburstApp(root, conn)
        root.protocol("WM_DELETE_WINDOW", lambda: (conn.close(), root.destroy()))
        root.mainloop()
    except Exception as e:
        messagebox.showerror("Критическая ошибка", str(e))
    finally:
        if conn:
            conn.close()
