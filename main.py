from kivy.app import App
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.button import Button
from kivy.uix.label import Label
from kivy.uix.textinput import TextInput
from kivy.uix.scrollview import ScrollView
from kivy.uix.popup import Popup
from kivy.uix.screenmanager import ScreenManager, Screen
from kivy.utils import platform
from kivy.clock import Clock
import sqlite3
from datetime import datetime, timedelta

class Database:
    def __init__(self):
        self.conn = sqlite3.connect('products.db')
        self.c = self.conn.cursor()
        self.c.execute('CREATE TABLE IF NOT EXISTS products (barcode TEXT PRIMARY KEY, name TEXT, exp TEXT, added TEXT)')
        self.conn.commit()
    def add(self, b, n, e):
        self.c.execute('INSERT OR REPLACE INTO products VALUES (?,?,?,?)', (b, n, e, datetime.now().strftime('%Y-%m-%d')))
        self.conn.commit()
    def all(self):
        self.c.execute('SELECT * FROM products ORDER BY exp')
        return self.c.fetchall()
    def delete(self, b):
        self.c.execute('DELETE FROM products WHERE barcode=?', (b,))
        self.conn.commit()
    def get(self, b):
        self.c.execute('SELECT * FROM products WHERE barcode=?', (b,))
        return self.c.fetchone()

class MainScreen(Screen):
    def on_enter(self):
        App.get_running_app().refresh()

class AddScreen(Screen):
    pass

class ExpirationApp(App):
    def build(self):
        self.db = Database()
        sm = ScreenManager()
        
        # MAIN
        ms = MainScreen(name='main')
        ml = BoxLayout(orientation='vertical', padding=10, spacing=10)
        ml.add_widget(Label(text='СРОКИ ГОДНОСТИ', bold=True, font_size=22, size_hint=(1,0.08)))
        bb = BoxLayout(size_hint=(1,0.08), spacing=10)
        bb.add_widget(Button(text='СКАНИРОВАТЬ', on_press=self.scan_barcode, background_color=(0.2,0.6,1,1)))
        bb.add_widget(Button(text='ДОБАВИТЬ', on_press=lambda x: setattr(sm,'current','add'), background_color=(0.2,0.8,0.2,1)))
        ml.add_widget(bb)
        sv = ScrollView()
        self.pl = BoxLayout(orientation='vertical', size_hint_y=None, spacing=2)
        self.pl.bind(minimum_height=self.pl.setter('height'))
        sv.add_widget(self.pl)
        ml.add_widget(sv)
        ms.add_widget(ml)
        sm.add_widget(ms)
        
        # ADD
        ads = AddScreen(name='add')
        al = BoxLayout(orientation='vertical', padding=20, spacing=10)
        al.add_widget(Label(text='ДОБАВИТЬ ПРОДУКТ', bold=True, font_size=18, size_hint=(1,0.08)))
        al.add_widget(Label(text='Название:'))
        self.ni = TextInput(hint_text='Молоко', multiline=False)
        al.add_widget(self.ni)
        al.add_widget(Label(text='Штрих-код:'))
        self.bi = TextInput(hint_text='4601234567890', multiline=False)
        al.add_widget(self.bi)
        al.add_widget(Label(text='Срок (ГГГГ-ММ-ДД):'))
        self.di = TextInput(text=(datetime.now()+timedelta(days=7)).strftime('%Y-%m-%d'), multiline=False)
        al.add_widget(self.di)
        bb3 = BoxLayout(size_hint=(1,0.1), spacing=10)
        bb3.add_widget(Button(text='СОХРАНИТЬ', on_press=self.save, background_color=(0.2,0.8,0.2,1)))
        bb3.add_widget(Button(text='ОТМЕНА', on_press=self.go_main))
        al.add_widget(bb3)
        ads.add_widget(al)
        sm.add_widget(ads)
        
        return sm
    
    def scan_barcode(self, instance):
        """Сканирование через ZXing (или ручной ввод на ПК)"""
        if platform == 'android':
            try:
                from plyer import barometer
                # На Android используем ZXing через Intent
                from jnius import autoclass
                PythonActivity = autoclass('org.kivy.android.PythonActivity')
                Intent = autoclass('android.content.Intent')
                
                intent = Intent('com.google.zxing.client.android.SCAN')
                intent.putExtra('SCAN_MODE', 'PRODUCT_MODE')
                PythonActivity.mActivity.startActivityForResult(intent, 0)
                
                # Ждём результат
                Clock.schedule_interval(self.check_scan_result, 0.5)
            except Exception as e:
                self.show_manual_input()
        else:
            self.show_manual_input()
    
    def check_scan_result(self, dt):
        """Проверка результата сканирования (для Android)"""
        try:
            from jnius import autoclass
            PythonActivity = autoclass('org.kivy.android.PythonActivity')
            activity = PythonActivity.mActivity
            
            if hasattr(activity, 'barcode_result'):
                barcode = activity.barcode_result
                delattr(activity, 'barcode_result')
                Clock.unschedule(self.check_scan_result)
                self.process_barcode(barcode)
        except:
            pass
    
    def show_manual_input(self):
        """Ручной ввод штрих-кода"""
        l = BoxLayout(orientation='vertical', padding=10, spacing=10)
        inp = TextInput(hint_text='Введите штрих-код', multiline=False)
        l.add_widget(inp)
        btn = Button(text='ПРОВЕРИТЬ', size_hint=(1,0.3))
        l.add_widget(btn)
        p = Popup(title='Ввод штрих-кода', content=l, size_hint=(0.8,0.3))
        def chk(inst):
            b = inp.text.strip()
            if b:
                p.dismiss()
                self.process_barcode(b)
        btn.bind(on_press=chk)
        p.open()
    
    def process_barcode(self, barcode):
        """Обработка найденного штрих-кода"""
        if not barcode:
            return
        
        prod = self.db.get(barcode)
        if prod:
            exp_date = datetime.strptime(prod[2], '%Y-%m-%d').date()
            today = datetime.now().date()
            if exp_date < today:
                sts, clr = 'ПРОСРОЧЕН!', (1,0.2,0.2,1)
            elif exp_date <= today + timedelta(days=3):
                sts, clr = 'Истекает', (1,0.6,0,1)
            else:
                sts, clr = 'Нормально', (0.2,0.8,0.2,1)
            p = Popup(title='Продукт найден', content=Label(text=f'{prod[1]}\nГоден до: {prod[2]}\n{sts}', color=clr), size_hint=(0.8,0.35))
            p.open()
        else:
            self.bi.text = barcode
            self.root.current = 'add'
    
    def save(self, instance):
        n = self.ni.text.strip()
        b = self.bi.text.strip()
        d = self.di.text.strip()
        if not n or not b or not d:
            Popup(title='Ошибка', content=Label(text='Заполните все поля!'), size_hint=(0.8,0.3)).open()
            return
        try:
            datetime.strptime(d, '%Y-%m-%d')
        except:
            Popup(title='Ошибка', content=Label(text='Неверная дата!'), size_hint=(0.8,0.3)).open()
            return
        self.db.add(b, n, d)
        self.ni.text = ''
        self.bi.text = ''
        self.root.current = 'main'
        Popup(title='OK', content=Label(text=f'{n} добавлен!'), size_hint=(0.8,0.3)).open()
    
    def go_main(self, *args):
        self.root.current = 'main'
    
    def refresh(self):
        self.pl.clear_widgets()
        prods = self.db.all()
        t = datetime.now().date()
        w = t + timedelta(days=3)
        if not prods:
            self.pl.add_widget(Label(text='Нет продуктов', size_hint_y=None, height=50))
            return
        for bc, nm, ex, ad in prods:
            ed = datetime.strptime(ex, '%Y-%m-%d').date()
            if ed < t:
                st, cl = 'ПРОСРОЧЕН', (1,0.2,0.2,1)
            elif ed <= w:
                st, cl = 'Истекает', (1,0.6,0,1)
            else:
                st, cl = 'OK', (0.2,0.8,0.2,1)
            card = BoxLayout(orientation='vertical', size_hint_y=None, height=90, padding=5)
            r1 = BoxLayout(size_hint_y=None, height=30)
            r1.add_widget(Label(text=nm, bold=True, color=cl, size_hint_x=0.6))
            r1.add_widget(Label(text=st, color=cl, size_hint_x=0.4))
            card.add_widget(r1)
            r2 = BoxLayout(size_hint_y=None, height=25)
            r2.add_widget(Label(text=f'Код: {bc}', size_hint_x=0.5))
            r2.add_widget(Label(text=f'Годен до: {ex}', size_hint_x=0.5))
            card.add_widget(r2)
            db = Button(text='Удалить', size_hint_y=None, height=30, background_color=(1,0.3,0.3,1))
            db.bind(on_press=lambda x, bc=bc: self.del_prod(bc))
            card.add_widget(db)
            self.pl.add_widget(card)
    
    def del_prod(self, bc):
        self.db.delete(bc)
        self.refresh()

if __name__ == '__main__':
    ExpirationApp().run()
