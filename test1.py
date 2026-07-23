import sqlite3
import pandas as pd
import plotly.express as px
import tkinter as tk
from tkinter import ttk, messagebox
import os

DB_FILE = 'engineering_hierarchy.db'
SQL_FILE = 'test123.db.sql'


def initialize_database():
    """Создает БД из SQL-скрипта, если её нет."""
    if not os.path.exists(DB_FILE):
        print(f"📦 БД не найдена. Создаём из {SQL_FILE}...")
        if not os.path.exists(SQL_FILE):
            raise FileNotFoundError(f"❌ Файл {SQL_FILE} не найден!")
        conn = sqlite3.connect(DB_FILE)
        with open(SQL_FILE, 'r', encoding='utf-8') as f:
            conn.executescript(f.read())
        conn.commit()
        print("✅ База данных успешно создана!")
    else:
        conn = sqlite3.connect(DB_FILE)
        print(f"✅ Подключено к существующей БД: {DB_FILE}")
    return conn


class SunburstApp:
    def __init__(self, root, conn):
        self.root = root
        self.conn = conn
        self.root.title("КИСУП: Полная иерархия ИСС с ранжированием по бюджету")
        self.root.geometry("750x350")
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
            root, values=self.industries, state="readonly", width=55, font=("Arial", 11))
        self.cb_industry.grid(row=0, column=1, pady=10)
        self.cb_industry.bind("<<ComboboxSelected>>", self.on_industry_change)
        self.cb_industry.current(0)

        tk.Label(root, text="🏢 Тип объекта:", font=("Arial", 12, "bold")).grid(
            row=1, column=0, sticky="w", pady=10)
        self.cb_object = ttk.Combobox(
            root, state="readonly", width=55, font=("Arial", 11))
        self.cb_object.grid(row=1, column=1, pady=10)

        self.btn_plot = tk.Button(
            root, text="📊 Построить полную иерархию (Sunburst)",
            command=self.generate_chart,
            bg="#4CAF50", fg="white", font=("Arial", 12, "bold"),
            padx=15, pady=8)
        self.btn_plot.grid(row=2, column=0, columnspan=2, pady=25)

        self.on_industry_change(None)

    def _get_industries(self):
        query = "SELECT DISTINCT industry FROM object_type ORDER BY industry;"
        df = pd.read_sql_query(query, self.conn)
        return df['industry'].tolist()

    def on_industry_change(self, event):
        selected_industry = self.cb_industry.get()
        query = """
            SELECT DISTINCT type_name 
            FROM object_type 
            WHERE industry = ? 
            ORDER BY type_name;
        """
        df = pd.read_sql_query(query, self.conn, params=(selected_industry,))
        self.cb_object['values'] = df['type_name'].tolist()
        if not df.empty:
            self.cb_object.current(0)

    def generate_chart(self):
        selected_type = self.cb_object.get()
        if not selected_type:
            messagebox.showwarning("Предупреждение", "Выберите тип объекта!")
            return

        # === SQL-запрос: полная иерархия с распределением доли RD между системами ===
        query = """
            SELECT 
                ot.industry                       AS "Отрасль",
                ot.type_name                      AS "Тип объекта",
                d.div_name                        AS "Division",
                p.pd_name                         AS "PD",
                r.rd_pref || ' — ' || r.rd_name   AS "RD",
                s.system_name                     AS "System",
                -- Доля системы = доля RD / кол-во систем в этом RD для данного типа объекта
                ROUND(rbs.budget_share * 1.0 / 
                    COUNT(s.system_id) OVER (PARTITION BY rbs.type_id, r.rd_id), 3
                ) AS "Доля бюджета (%)"
            FROM rd_budget_share rbs
            JOIN object_type ot ON rbs.type_id = ot.type_id
            JOIN rd            r  ON rbs.rd_id  = r.rd_id
            JOIN pd            p  ON r.pd_name  = p.pd_name
            JOIN division      d  ON p.div_id   = d.div_id
            JOIN system        s  ON s.rd_id    = r.rd_id
            WHERE ot.type_name = ?
              AND rbs.budget_share > 0
            ORDER BY 
                "Доля бюджета (%)" DESC,
                d.div_name, p.pd_name, r.rd_pref, s.system_name;
        """

        try:
            df = pd.read_sql_query(query, self.conn, params=(selected_type,))

            if df.empty:
                messagebox.showinfo(
                    "Информация",
                    f"Для объекта '{selected_type}' нет данных в справочнике.")
                return

            total_share = df["Доля бюджета (%)"].sum()
            print(f"\n📊 Найдено {len(df)} систем. Общая доля ИСС: {total_share:.2f}%\n")

            # === Построение Sunburst с полной иерархией ===
            path = ["Отрасль", "Тип объекта", "Division", "PD", "RD", "System"]

            fig = px.sunburst(
                df,
                path=path,
                values="Доля бюджета (%)",
                title=(
                    f"Полная иерархия ИСС: {selected_type}\n"
                    f"Отрасль → Тип объекта → Division → PD → RD → System\n"
                    f"(Размер сектора = доля в бюджете, ранжирование по убыванию)"
                ),
                color="Доля бюджета (%)",
                color_continuous_scale="Viridis",
                hover_data={
                    "Доля бюджета (%)": ":.3f",
                    "Отрасль": True,
                    "Тип объекта": True,
                    "Division": True,
                    "PD": True,
                    "RD": True,
                    "System": True
                },
                branchvalues="total",
                maxdepth=6
            )

            fig.update_traces(
                textinfo="label+percent entry",
                insidetextorientation='radial',
                textfont_size=11,
                marker=dict(line=dict(width=1.5, color='white')),
                # Сортировка секторов по убыванию доли бюджета (ранжирование)
                sort=False
            )

            fig.update_layout(
                margin=dict(t=80, l=0, r=0, b=0),
                font=dict(family="Arial, sans-serif"),
                width=1400,
                height=1400,
                legend=dict(orientation="h", yanchor="bottom", y=-0.1)
            )

            # Сохраняем HTML для GitHub Actions
            output_file = "index.html"
            fig.write_html(output_file)
            print(f"✅ Файл {output_file} успешно создан!")

            # Открываем в браузере (локально)
            try:
                fig.show()
            except Exception:
                pass  # На сервере GitHub браузера нет — это нормально

            # === Печатаем ранжирование в консоль ===
            print("\n" + "=" * 90)
            print(f"📋 РАНЖИРОВАНИЕ ПО РАЗДЕЛАМ (RD) для объекта: {selected_type}")
            print("=" * 90)
            rd_summary = df.groupby(["Division", "PD", "RD"])["Доля бюджета (%)"].sum().reset_index()
            rd_summary = rd_summary.sort_values("Доля бюджета (%)", ascending=False)
            print(rd_summary.to_string(index=False))
            print(f"\n💰 ИТОГО доля ИСС: {total_share:.2f}% от общестроительного бюджета")
            print("=" * 90)

        except Exception as e:
            messagebox.showerror("Ошибка", f"Не удалось построить диаграмму:\n{e}")
            import traceback
            traceback.print_exc()


if __name__ == "__main__":
    conn = None
    try:
        conn = initialize_database()
        root = tk.Tk()
        app = SunburstApp(root, conn)
        root.protocol("WM_DELETE_WINDOW", lambda: (conn.close(), root.destroy()))
        root.mainloop()
    except Exception as e:
        print(f"❌ Критическая ошибка: {e}")
        import traceback
        traceback.print_exc()
    finally:
        if conn:
            conn.close()
