from kivy.app import App
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.button import Button
from kivy.uix.label import Label
from kivy.uix.textinput import TextInput
from kivy.uix.scrollview import ScrollView
from kivy.uix.popup import Popup
from kivy.uix.screenmanager import ScreenManager, Screen
from kivy.uix.camera import Camera
from kivy.clock import Clock
import sqlite3
from datetime import datetime, timedelta
import numpy as np
from pyzbar.pyzbar import decode


class Database:
    def __init__(self):
        self.conn = sqlite3.connect('products.db')
        self.c = self.conn.cursor()
        self.c.execute(
            'CREATE TABLE IF NOT EXISTS products (barcode TEXT PRIMARY KEY, name TEXT, exp TEXT, added TEXT)')
        self.conn.commit()

    def add(self, b, n, e):
        self.c.execute('INSERT OR REPLACE INTO products VALUES (?,?,?,?)',
                       (b, n, e, datetime.now().strftime('%Y-%m-%d')))
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


class ScanScreen(Screen):
    def on_enter(self):
        App.get_running_app().start_cam()

    def on_leave(self):
        App.get_running_app().stop_cam()


class AddScreen(Screen):
    pass


class ExpirationApp(App):
    def build(self):
        self.db = Database()
        self.last_barcode = None
        sm = ScreenManager()

        # MAIN SCREEN
        ms = MainScreen(name='main')
        ml = BoxLayout(orientation='vertical', padding=10, spacing=10)
        ml.add_widget(Label(text='СРОКИ ГОДНОСТИ', bold=True, font_size=22, size_hint=(1, 0.08)))
        bb = BoxLayout(size_hint=(1, 0.08), spacing=10)
        bb.add_widget(Button(text='СКАНИРОВАТЬ', on_press=lambda x: setattr(sm, 'current', 'scan'),
                             background_color=(0.2, 0.6, 1, 1)))
        bb.add_widget(Button(text='ДОБАВИТЬ', on_press=lambda x: setattr(sm, 'current', 'add'),
                             background_color=(0.2, 0.8, 0.2, 1)))
        ml.add_widget(bb)
        sv = ScrollView()
        self.pl = BoxLayout(orientation='vertical', size_hint_y=None, spacing=2)
        self.pl.bind(minimum_height=self.pl.setter('height'))
        sv.add_widget(self.pl)
        ml.add_widget(sv)
        ms.add_widget(ml)
        sm.add_widget(ms)

        # SCAN SCREEN
        ss = ScanScreen(name='scan')
        sl = BoxLayout(orientation='vertical')
        self.cb = BoxLayout()
        sl.add_widget(self.cb)
        bb2 = BoxLayout(size_hint=(1, 0.1), spacing=10, padding=10)
        bb2.add_widget(Button(text='НАЗАД', on_press=lambda x: self.go_main()))
        bb2.add_widget(Button(text='ВВЕСТИ ВРУЧНУЮ', on_press=self.manual))
        sl.add_widget(bb2)
        self.st = Label(text='Наведите камеру на штрих-код', size_hint=(1, 0.08))
        sl.add_widget(self.st)
        ss.add_widget(sl)
        sm.add_widget(ss)

        # ADD SCREEN
        ads = AddScreen(name='add')
        al = BoxLayout(orientation='vertical', padding=20, spacing=10)
        al.add_widget(Label(text='ДОБАВИТЬ ПРОДУКТ', bold=True, font_size=18, size_hint=(1, 0.08)))
        al.add_widget(Label(text='Название:'))
        self.ni = TextInput(hint_text='Молоко', multiline=False)
        al.add_widget(self.ni)
        al.add_widget(Label(text='Штрих-код:'))
        self.bi = TextInput(hint_text='Отсканируется автоматически', multiline=False)
        al.add_widget(self.bi)
        al.add_widget(Label(text='Срок (ГГГГ-ММ-ДД):'))
        self.di = TextInput(text=(datetime.now() + timedelta(days=7)).strftime('%Y-%m-%d'), multiline=False)
        al.add_widget(self.di)
        bb3 = BoxLayout(size_hint=(1, 0.1), spacing=10)
        bb3.add_widget(Button(text='СОХРАНИТЬ', on_press=self.save, background_color=(0.2, 0.8, 0.2, 1)))
        bb3.add_widget(Button(text='ОТМЕНА', on_press=lambda x: self.go_main()))
        al.add_widget(bb3)
        ads.add_widget(al)
        sm.add_widget(ads)

        return sm

    def start_cam(self):
        try:
            self.cam = Camera(resolution=(640, 480), play=True)
            self.cb.clear_widgets()
            self.cb.add_widget(self.cam)
            self.last_barcode = None
            Clock.schedule_interval(self.scan_frame, 0.5)
            self.st.text = 'Наведите камеру на штрих-код'
        except Exception as e:
            self.st.text = f'Ошибка камеры: {str(e)}'

    def stop_cam(self):
        Clock.unschedule(self.scan_frame)
        if hasattr(self, 'cam'):
            self.cam.play = False
            self.cb.clear_widgets()

    def scan_frame(self, dt):
        if not hasattr(self, 'cam') or not self.cam.texture:
            return
        try:
            pixels = np.frombuffer(self.cam.texture.pixels, dtype=np.uint8)
            frame = pixels.reshape(self.cam.texture.height, self.cam.texture.width, 4)
            gray = np.dot(frame[..., :3], [0.299, 0.587, 0.114]).astype(np.uint8)
            barcodes = decode(gray)
            for b in barcodes:
                barcode_data = b.data.decode('utf-8')
                if barcode_data != self.last_barcode:
                    self.last_barcode = barcode_data
                    self.st.text = f'Найден: {barcode_data}'
                    prod = self.db.get(barcode_data)
                    if prod:
                        exp_date = datetime.strptime(prod[2], '%Y-%m-%d').date()
                        today = datetime.now().date()
                        if exp_date < today:
                            sts, clr = 'ПРОСРОЧЕН!', (1, 0.2, 0.2, 1)
                        elif exp_date <= today + timedelta(days=3):
                            sts, clr = 'Истекает', (1, 0.6, 0, 1)
                        else:
                            sts, clr = 'Нормально', (0.2, 0.8, 0.2, 1)
                        p = Popup(title='Продукт найден',
                                  content=Label(text=f'{prod[1]}\nГоден до: {prod[2]}\n{sts}', color=clr),
                                  size_hint=(0.8, 0.35))
                        p.open()
                    else:
                        Clock.schedule_once(lambda dt, bc=barcode_data: self.go_add(bc), 0.5)
                    Clock.schedule_once(lambda dt: self.reset_barcode(), 2)
        except:
            pass

    def reset_barcode(self):
        self.last_barcode = None

    def go_add(self, bc=''):
        if bc:
            self.bi.text = bc
        self.root.current = 'add'

    def go_main(self):
        self.stop_cam()
        self.root.current = 'main'

    def manual(self, instance):
        l = BoxLayout(orientation='vertical', padding=10, spacing=10)
        inp = TextInput(hint_text='Штрих-код', multiline=False)
        l.add_widget(inp)
        btn = Button(text='ПРОВЕРИТЬ', size_hint=(1, 0.3))
        l.add_widget(btn)
        p = Popup(title='Ввод', content=l, size_hint=(0.8, 0.3))

        def chk(inst):
            b = inp.text
            p.dismiss()
            if b:
                prod = self.db.get(b)
                if prod:
                    Popup(title='Найден', content=Label(text=f'{prod[1]}\nГоден до: {prod[2]}'),
                          size_hint=(0.8, 0.3)).open()
                else:
                    self.go_add(b)

        btn.bind(on_press=chk)
        p.open()

    def save(self, instance):
        n = self.ni.text.strip()
        b = self.bi.text.strip()
        d = self.di.text.strip()
        if not n or not b or not d:
            Popup(title='Ошибка', content=Label(text='Заполните все поля!'), size_hint=(0.8, 0.3)).open()
            return
        try:
            datetime.strptime(d, '%Y-%m-%d')
        except:
            Popup(title='Ошибка', content=Label(text='Неверная дата!'), size_hint=(0.8, 0.3)).open()
            return
        self.db.add(b, n, d)
        self.ni.text = ''
        self.bi.text = ''
        self.go_main()
        Popup(title='OK', content=Label(text=f'{n} добавлен!'), size_hint=(0.8, 0.3)).open()

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
                st, cl = 'ПРОСРОЧЕН', (1, 0.2, 0.2, 1)
            elif ed <= w:
                st, cl = 'Истекает', (1, 0.6, 0, 1)
            else:
                st, cl = 'OK', (0.2, 0.8, 0.2, 1)
            card = BoxLayout(orientation='vertical', size_hint_y=None, height=90, padding=5)
            r1 = BoxLayout(size_hint_y=None, height=30)
            r1.add_widget(Label(text=nm, bold=True, color=cl, size_hint_x=0.6))
            r1.add_widget(Label(text=st, color=cl, size_hint_x=0.4))
            card.add_widget(r1)
            r2 = BoxLayout(size_hint_y=None, height=25)
            r2.add_widget(Label(text=f'Код: {bc}', size_hint_x=0.5))
            r2.add_widget(Label(text=f'Годен до: {ex}', size_hint_x=0.5))
            card.add_widget(r2)
            db = Button(text='Удалить', size_hint_y=None, height=30, background_color=(1, 0.3, 0.3, 1))
            db.bind(on_press=lambda x, bc=bc: self.del_prod(bc))
            card.add_widget(db)
            self.pl.add_widget(card)

    def del_prod(self, bc):
        self.db.delete(bc)
        self.refresh()


if __name__ == '__main__':
    ExpirationApp().run()