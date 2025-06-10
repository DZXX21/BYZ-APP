from flask import Flask, render_template, request, redirect, url_for, send_file
from flask_mysqldb import MySQL
from decimal import Decimal
from io import BytesIO
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.lib.units import mm
import os

app = Flask(__name__)

# MySQL Config
app.config['MYSQL_HOST'] = 'localhost'
app.config['MYSQL_USER'] = 'root'
app.config['MYSQL_PASSWORD'] = ''
app.config['MYSQL_DB'] = 'teklif_sistemi'
app.config['MYSQL_CURSORCLASS'] = 'DictCursor'

# Türkçe karakter desteği için fontu yükle
FONT_PATH = "fonts/DejaVuSans.ttf"
LOGO_PATH = "static/img/logo.png"

# Font yükleme kontrolü
try:
    if os.path.exists(FONT_PATH):
        pdfmetrics.registerFont(TTFont("DejaVuSans", FONT_PATH))
        FONT_AVAILABLE = True
    else:
        FONT_AVAILABLE = False
        print("Uyarı: fonts/DejaVuSans.ttf bulunamadı! Helvetica kullanılacak.")
except Exception as e:
    FONT_AVAILABLE = False
    print(f"Font yükleme hatası: {e}")

mysql = MySQL(app)

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/personel-ekle', methods=['GET', 'POST'])
def personel_ekle():
    if request.method == 'POST':
        ad = request.form['ad']
        pozisyon = request.form['pozisyon']
        telefon = request.form['telefon']
        eposta = request.form['eposta']
        adres = request.form['adres']
        gunluk_maas = request.form['gunluk_maas']

        cur = mysql.connection.cursor()
        cur.execute("""
            INSERT INTO personel (ad, pozisyon, telefon, eposta, adres, gunluk_maas)
            VALUES (%s, %s, %s, %s, %s, %s)
        """, (ad, pozisyon, telefon, eposta, adres, gunluk_maas))
        mysql.connection.commit()
        cur.close()
        return redirect(url_for('index'))
    return render_template('personel_ekle.html')

@app.route('/urun-ekle', methods=['GET', 'POST'])
def urun_ekle():
    if request.method == 'POST':
        ad = request.form['ad']
        adet = request.form['adet']
        renk = request.form['renk']
        boyut_cm = request.form['boyut_cm']
        birim_fiyat = request.form['birim_fiyat']
        kdv_orani = float(request.form['kdv_orani'])
        
        # KDV oranı kontrolü - eğer 1'den büyükse yüzde olarak girilmiş, 100'e böl
        if kdv_orani > 1:
            kdv_orani = kdv_orani / 100
        
        cur = mysql.connection.cursor()
        cur.execute("""
            INSERT INTO urun (ad, adet, renk, boyut_cm, birim_fiyat, kdv_orani)
            VALUES (%s, %s, %s, %s, %s, %s)
        """, (ad, adet, renk, boyut_cm, birim_fiyat, kdv_orani))
        mysql.connection.commit()
        cur.close()
        return redirect(url_for('index'))
    return render_template('urun_ekle.html')

@app.route('/musteri-ekle', methods=['GET', 'POST'])
def musteri_ekle():
    if request.method == 'POST':
        ad = request.form['ad']
        soyad = request.form['soyad']
        firma_adi = request.form['firma_adi']
        vergi_no = request.form['vergi_no']
        email = request.form['email']
        telefon = request.form['telefon']

        cur = mysql.connection.cursor()
        cur.execute("""
            INSERT INTO musteri (ad, soyad, firma_adi, vergi_no, email, telefon)
            VALUES (%s, %s, %s, %s, %s, %s)
        """, (ad, soyad, firma_adi, vergi_no, email, telefon))
        mysql.connection.commit()
        cur.close()
        return redirect(url_for('index'))
    return render_template('musteri_ekle.html')

@app.route('/teklif-olustur', methods=['GET', 'POST'])
def teklif_olustur():
    cur = mysql.connection.cursor()

    if request.method == 'POST':
        musteri_id = request.form['musteri_id']
        kar_orani = Decimal(request.form['kar_orani'])
        secilen_personeller = request.form.getlist('personel_id')
        secilen_urunler = request.form.getlist('urun_id')

        toplam_maas = Decimal(0)
        toplam_urun_fiyati = Decimal(0)
        toplam_gun = 0

        for pid in secilen_personeller:
            gun = int(request.form.get(f'gun_{pid}', 1))
            toplam_gun += gun
            cur.execute("SELECT gunluk_maas FROM personel WHERE id = %s", [pid])
            maas = cur.fetchone()['gunluk_maas']
            toplam_maas += Decimal(maas) * gun

        for uid in secilen_urunler:
            adet = int(request.form.get(f"urun_adet_{uid}", 1))
            cur.execute("SELECT birim_fiyat, kdv_orani FROM urun WHERE id = %s", [uid])
            urun = cur.fetchone()
            fiyat = Decimal(urun['birim_fiyat'])
            kdv = Decimal(urun['kdv_orani'])
            toplam_urun_fiyati += adet * fiyat * (1 + kdv)

        toplam = toplam_maas + toplam_urun_fiyati
        toplam += toplam * kar_orani

        cur.execute("INSERT INTO teklif (musteri_id, gun_sayisi, kar_orani, toplam_fiyat) VALUES (%s, %s, %s, %s)",
                    (musteri_id, toplam_gun, float(kar_orani), float(toplam)))
        teklif_id = cur.lastrowid

        for pid in secilen_personeller:
            cur.execute("INSERT INTO teklif_personel (teklif_id, personel_id) VALUES (%s, %s)", (teklif_id, pid))

        for uid in secilen_urunler:
            adet = int(request.form.get(f"urun_adet_{uid}", 1))
            cur.execute("INSERT INTO teklif_urun (teklif_id, urun_id, miktar) VALUES (%s, %s, %s)",
                        (teklif_id, uid, adet))

        mysql.connection.commit()
        cur.close()
        return f"<h2>Teklif başarıyla oluşturuldu</h2><p>Toplam Tutar: {toplam:.2f} ₺</p><a href='/'>Ana Sayfa</a>"

    cur.execute("SELECT * FROM musteri")
    musteriler = cur.fetchall()

    cur.execute("SELECT * FROM personel WHERE aktif = TRUE")
    personeller = cur.fetchall()

    cur.execute("SELECT * FROM urun")
    urunler = cur.fetchall()

    cur.close()
    return render_template('teklif_olustur.html', musteriler=musteriler, personeller=personeller, urunler=urunler)

@app.route('/teklifler')
def teklifler():
    cur = mysql.connection.cursor()
    cur.execute("""
        SELECT t.id, t.tarih, t.toplam_fiyat, m.ad, m.soyad, m.firma_adi
        FROM teklif t
        JOIN musteri m ON t.musteri_id = m.id
        ORDER BY t.id DESC
    """)
    teklifler = cur.fetchall()
    cur.close()
    return render_template('teklif_liste.html', teklifler=teklifler)

# ==================== İŞ TAKİP SİSTEMİ ====================

@app.route('/is-takip')
def is_takip():
    cur = mysql.connection.cursor()
    
    # Aktif personelleri getir
    cur.execute("SELECT * FROM personel WHERE aktif = TRUE ORDER BY ad")
    personeller = cur.fetchall()
    
    # Bugünün kayıtlarını getir
    from datetime import date
    bugun = date.today()
    
    cur.execute("""
        SELECT pt.*, p.ad, p.pozisyon 
        FROM personel_takip pt
        JOIN personel p ON pt.personel_id = p.id
        WHERE DATE(pt.tarih) = %s
        ORDER BY pt.tarih DESC
    """, [bugun])
    bugun_kayitlari = cur.fetchall()
    
    cur.close()
    return render_template('is_takip.html', personeller=personeller, bugun_kayitlari=bugun_kayitlari, bugun=bugun)

@app.route('/personel-giris', methods=['POST'])
def personel_giris():
    personel_id = request.form['personel_id']
    tarih = request.form.get('tarih', '')  # Özel tarih seçimi
    aciklama = request.form.get('aciklama', '')
    
    cur = mysql.connection.cursor()
    
    # Eğer tarih belirtilmemişse bugünü kullan
    if not tarih:
        from datetime import datetime
        tarih = datetime.now().strftime('%Y-%m-%d')
    
    # Bu personel bu tarihte zaten kayıt yapmış mı kontrol et
    cur.execute("""
        SELECT id FROM personel_takip 
        WHERE personel_id = %s AND DATE(tarih) = %s
    """, [personel_id, tarih])
    
    if cur.fetchone():
        cur.close()
        return f"Bu personel {tarih} tarihinde zaten kayıt yapılmış!", 400
    
    # Giriş kaydı ekle (belirtilen tarih ile)
    cur.execute("""
        INSERT INTO personel_takip (personel_id, tarih, durum, aciklama)
        VALUES (%s, %s, 'giris', %s)
    """, (personel_id, tarih + ' 08:00:00', aciklama))  # Varsayılan saat 08:00
    
    mysql.connection.commit()
    cur.close()
    return redirect(url_for('is_takip'))

@app.route('/toplu-giris', methods=['POST'])
def toplu_giris():
    personel_ids = request.form.getlist('personel_ids')
    tarih = request.form['tarih']
    aciklama = request.form.get('aciklama', 'Toplu kayıt')
    
    if not personel_ids:
        return "Hiç personel seçilmedi!", 400
    
    cur = mysql.connection.cursor()
    
    basarili = 0
    hatali = []
    
    for personel_id in personel_ids:
        # Bu personel bu tarihte zaten kayıt yapmış mı kontrol et
        cur.execute("""
            SELECT id FROM personel_takip 
            WHERE personel_id = %s AND DATE(tarih) = %s
        """, [personel_id, tarih])
        
        if cur.fetchone():
            # Personel adını al
            cur.execute("SELECT ad FROM personel WHERE id = %s", [personel_id])
            personel_ad = cur.fetchone()['ad']
            hatali.append(personel_ad)
            continue
        
        # Giriş kaydı ekle
        cur.execute("""
            INSERT INTO personel_takip (personel_id, tarih, durum, aciklama)
            VALUES (%s, %s, 'giris', %s)
        """, (personel_id, tarih + ' 08:00:00', aciklama))
        basarili += 1
    
    mysql.connection.commit()
    cur.close()
    
    mesaj = f"{basarili} personel başarıyla kaydedildi."
    if hatali:
        mesaj += f" Zaten kayıtlı olanlar: {', '.join(hatali)}"
    
    return f"<h3>{mesaj}</h3><a href='{url_for('is_takip')}'>Geri Dön</a>"

@app.route('/kayit-sil/<int:kayit_id>')
def kayit_sil(kayit_id):
    cur = mysql.connection.cursor()
    cur.execute("DELETE FROM personel_takip WHERE id = %s", [kayit_id])
    mysql.connection.commit()
    cur.close()
    return redirect(url_for('is_takip'))

# ==================== NAKİT AVANS SİSTEMİ ====================

@app.route('/nakit-avans')
def nakit_avans():
    cur = mysql.connection.cursor()
    
    # Aktif personelleri getir
    cur.execute("SELECT * FROM personel WHERE aktif = TRUE ORDER BY ad")
    personeller = cur.fetchall()
    
    # Bu ayki avans kayıtlarını getir
    from datetime import date
    bugun = date.today()
    
    cur.execute("""
        SELECT na.*, p.ad, p.pozisyon 
        FROM nakit_avans na
        JOIN personel p ON na.personel_id = p.id
        WHERE MONTH(na.tarih) = %s AND YEAR(na.tarih) = %s
        ORDER BY na.tarih DESC
    """, [bugun.month, bugun.year])
    bu_ay_avanslar = cur.fetchall()
    
    cur.close()
    return render_template('nakit_avans.html', personeller=personeller, bu_ay_avanslar=bu_ay_avanslar)

@app.route('/avans-ver', methods=['POST'])
def avans_ver():
    personel_id = request.form['personel_id']
    miktar = float(request.form['miktar'])
    aciklama = request.form.get('aciklama', '')
    tarih = request.form.get('tarih', '')
    
    if miktar <= 0:
        return "Avans miktarı 0'dan büyük olmalıdır!", 400
    
    cur = mysql.connection.cursor()
    
    # Eğer tarih belirtilmemişse bugünü kullan
    if not tarih:
        from datetime import datetime
        tarih = datetime.now().strftime('%Y-%m-%d')
    
    # Avans kaydı ekle
    cur.execute("""
        INSERT INTO nakit_avans (personel_id, miktar, tarih, aciklama)
        VALUES (%s, %s, %s, %s)
    """, (personel_id, miktar, tarih, aciklama))
    
    mysql.connection.commit()
    cur.close()
    return redirect(url_for('nakit_avans'))

@app.route('/avans-sil/<int:avans_id>')
def avans_sil(avans_id):
    cur = mysql.connection.cursor()
    cur.execute("DELETE FROM nakit_avans WHERE id = %s", [avans_id])
    mysql.connection.commit()
    cur.close()
    return redirect(url_for('nakit_avans'))

@app.route('/personel-rapor')
def personel_rapor():
    cur = mysql.connection.cursor()
    
    # Ay/yıl parametresi al (varsayılan: bu ay)
    from datetime import date
    ay = request.args.get('ay', date.today().month)
    yil = request.args.get('yil', date.today().year)
    personel_id = request.args.get('personel_id', '')  # Personel filtresi
    
    # Tüm personel listesi (filtre için)
    cur.execute("SELECT * FROM personel WHERE aktif = TRUE ORDER BY ad")
    tum_personeller = cur.fetchall()
    
    # Personel listesi (filtre varsa sadece o personel)
    if personel_id:
        cur.execute("SELECT * FROM personel WHERE id = %s AND aktif = TRUE", [personel_id])
        personeller = cur.fetchall()
    else:
        personeller = tum_personeller
    
    # Her personel için çalışma günlerini ve avansları hesapla
    personel_raporu = []
    
    for p in personeller:
        # Bu personelin bu aydaki giriş kayıtlarını say
        cur.execute("""
            SELECT COUNT(DISTINCT DATE(tarih)) as calisma_gunu
            FROM personel_takip 
            WHERE personel_id = %s 
            AND MONTH(tarih) = %s 
            AND YEAR(tarih) = %s 
            AND durum = 'giris'
        """, [p['id'], ay, yil])
        
        result = cur.fetchone()
        calisma_gunu = result['calisma_gunu'] if result else 0
        
        # Bu ayki toplam avansı hesapla
        cur.execute("""
            SELECT COALESCE(SUM(miktar), 0) as toplam_avans
            FROM nakit_avans 
            WHERE personel_id = %s 
            AND MONTH(tarih) = %s 
            AND YEAR(tarih) = %s
        """, [p['id'], ay, yil])
        
        avans_result = cur.fetchone()
        toplam_avans = float(avans_result['toplam_avans']) if avans_result else 0
        
        # Maaş hesapla
        gunluk_maas = float(p['gunluk_maas'])
        brut_maas = calisma_gunu * gunluk_maas
        net_maas = brut_maas - toplam_avans
        
        personel_raporu.append({
            'personel': p,
            'calisma_gunu': calisma_gunu,
            'gunluk_maas': gunluk_maas,
            'brut_maas': brut_maas,
            'toplam_avans': toplam_avans,
            'net_maas': net_maas
        })
    
    cur.close()
    
    # Ay isimlerini Türkçe yap
    ay_isimleri = {
        1: 'Ocak', 2: 'Şubat', 3: 'Mart', 4: 'Nisan', 5: 'Mayıs', 6: 'Haziran',
        7: 'Temmuz', 8: 'Ağustos', 9: 'Eylül', 10: 'Ekim', 11: 'Kasım', 12: 'Aralık'
    }
    
    return render_template('personel_rapor.html', 
                         personel_raporu=personel_raporu,
                         tum_personeller=tum_personeller,  # Filtre için gerekli
                         ay=int(ay), 
                         yil=int(yil),
                         ay_adi=ay_isimleri[int(ay)])

@app.route('/personel-detay/<int:personel_id>')
def personel_detay(personel_id):
    cur = mysql.connection.cursor()
    
    # Personel bilgisi
    cur.execute("SELECT * FROM personel WHERE id = %s", [personel_id])
    personel = cur.fetchone()
    
    if not personel:
        return "Personel bulunamadı!", 404
    
    # Ay/yıl parametresi
    from datetime import date
    ay = request.args.get('ay', date.today().month)
    yil = request.args.get('yil', date.today().year)
    
    # Bu personelin detaylı iş kayıtları
    cur.execute("""
        SELECT DATE(tarih) as tarih_gun, 
               MIN(TIME(tarih)) as giris_saati,
               GROUP_CONCAT(CASE WHEN aciklama != '' THEN aciklama END SEPARATOR ', ') as aciklamalar
        FROM personel_takip 
        WHERE personel_id = %s 
        AND MONTH(tarih) = %s 
        AND YEAR(tarih) = %s
        GROUP BY DATE(tarih)
        ORDER BY DATE(tarih) DESC
    """, [personel_id, ay, yil])
    
    is_kayitlari = cur.fetchall()
    
    # Bu personelin bu ayki avans kayıtları
    cur.execute("""
        SELECT DATE(tarih) as tarih_gun, miktar, aciklama
        FROM nakit_avans 
        WHERE personel_id = %s 
        AND MONTH(tarih) = %s 
        AND YEAR(tarih) = %s
        ORDER BY DATE(tarih) DESC
    """, [personel_id, ay, yil])
    
    avans_kayitlari = cur.fetchall()
    
    # Hesaplamalar
    calisma_gunu = len([k for k in is_kayitlari if k['giris_saati']])
    brut_maas = calisma_gunu * float(personel['gunluk_maas'])
    toplam_avans = sum([float(a['miktar']) for a in avans_kayitlari])
    net_maas = brut_maas - toplam_avans
    
    cur.close()
    
    ay_isimleri = {
        1: 'Ocak', 2: 'Şubat', 3: 'Mart', 4: 'Nisan', 5: 'Mayıs', 6: 'Haziran',
        7: 'Temmuz', 8: 'Ağustos', 9: 'Eylül', 10: 'Ekim', 11: 'Kasım', 12: 'Aralık'
    }
    
    return render_template('personel_detay.html', 
                         personel=personel,
                         is_kayitlari=is_kayitlari,
                         avans_kayitlari=avans_kayitlari,
                         calisma_gunu=calisma_gunu,
                         brut_maas=brut_maas,
                         toplam_avans=toplam_avans,
                         net_maas=net_maas,
                         ay=int(ay),
                         yil=int(yil),
                         ay_adi=ay_isimleri[int(ay)])

@app.route('/teklif/<int:teklif_id>/pdf')
def teklif_pdf(teklif_id):
    cur = mysql.connection.cursor()
    
    # Teklif ve müşteri bilgisi
    cur.execute("""
        SELECT t.*, m.ad, m.soyad, m.firma_adi, m.vergi_no
        FROM teklif t
        JOIN musteri m ON t.musteri_id = m.id
        WHERE t.id = %s
    """, [teklif_id])
    teklif = cur.fetchone()
    
    if not teklif:
        return "Teklif bulunamadi!", 404
    
    # Personeller
    cur.execute("""
        SELECT p.ad, p.pozisyon, p.gunluk_maas
        FROM teklif_personel tp
        JOIN personel p ON tp.personel_id = p.id
        WHERE tp.teklif_id = %s
    """, [teklif_id])
    personeller = cur.fetchall()
    
    # Ürünler
    cur.execute("""
        SELECT u.ad, tu.miktar, u.birim_fiyat, u.kdv_orani
        FROM teklif_urun tu
        JOIN urun u ON tu.urun_id = u.id
        WHERE tu.teklif_id = %s
    """, [teklif_id])
    urunler = cur.fetchall()
    
    cur.close()
    
    # PDF oluşturma
    buffer = BytesIO()
    pdf = canvas.Canvas(buffer, pagesize=A4)
    width, height = A4
    
    # Türkçe karakterleri temizleyen fonksiyon
    def temizle_turkce(metin):
        if metin is None:
            return ""
        metin = str(metin)
        turkce_karakter = {
            'ç': 'c', 'Ç': 'C', 'ğ': 'g', 'Ğ': 'G', 'ı': 'i', 'İ': 'I', 
            'ö': 'o', 'Ö': 'O', 'ş': 's', 'Ş': 'S', 'ü': 'u', 'Ü': 'U'
        }
        for tr, en in turkce_karakter.items():
            metin = metin.replace(tr, en)
        return metin
    
    # Font ayarı - sadece Helvetica kullan
    pdf.setFont("Helvetica", 10)
    
    # Başlık bölümü - Logo ve firma bilgileri
    y = height - 40
    
    # Üst bilgi kutusu
    pdf.rect(30, y - 80, width - 60, 80, fill=0)
    
    # Logo (sol üst)
    if os.path.exists(LOGO_PATH):
        try:
            pdf.drawImage(LOGO_PATH, 40, y - 70, width=80, height=60, preserveAspectRatio=True)
        except:
            pass
    
    # Firma bilgileri (orta üst)
    pdf.setFont("Helvetica-Bold", 18)
    pdf.drawString(140, y - 25, "BYZDIZAYN INSAAT")
    
    pdf.setFont("Helvetica", 11)
    pdf.drawString(140, y - 42, "Adres: Antalya, Turkiye")
    pdf.drawString(140, y - 55, "Tel: 0544 681 19 91")
    pdf.drawString(140, y - 68, "Email: info@byzdizayn.com")
    
    # Teklif ID ve tarih (sag ust - kutu içinde)
    pdf.setFillGray(0.9)
    pdf.rect(width - 140, y - 70, 120, 60, fill=1)
    pdf.setFillGray(0)  # Siyaha geri döndür
    
    pdf.setFont("Helvetica-Bold", 12)
    pdf.drawString(width - 130, y - 20, "TEKLIF NO")
    pdf.setFont("Helvetica-Bold", 16)
    pdf.drawString(width - 130, y - 35, f"#{teklif['id']:04d}")
    
    pdf.setFont("Helvetica", 10)
    pdf.drawString(width - 130, y - 50, f"Tarih:")
    pdf.drawString(width - 130, y - 62, f"{teklif['tarih']}")
    
    # Ana çizgi
    pdf.line(30, y - 90, width - 30, y - 90)
    
    # Müşteri bilgileri kutusu
    y -= 130
    pdf.rect(30, y - 80, width - 60, 80, fill=0)
    
    # Başlık bölümü
    pdf.setFillGray(0.8)
    pdf.rect(30, y - 20, width - 60, 20, fill=1)
    pdf.setFillGray(0)  # Siyaha geri döndür
    
    pdf.setFont("Helvetica-Bold", 12)
    pdf.drawString(40, y - 15, "MUSTERI BILGILERI")
    
    pdf.setFont("Helvetica", 11)
    pdf.drawString(40, y - 35, f"Musteri: {temizle_turkce(teklif['ad'])} {temizle_turkce(teklif['soyad'])}")
    pdf.drawString(40, y - 50, f"Firma: {temizle_turkce(teklif['firma_adi'])}")
    pdf.drawString(40, y - 65, f"Vergi No: {teklif['vergi_no']}")
    
    # Personel toplam maliyeti
    y -= 110
    if personeller:
        pdf.setFont("Helvetica-Bold", 12)
        pdf.drawString(40, y, "PERSONEL MALIYETI")
        y -= 20
        
        # Personel toplam hesaplama
        personel_toplam = 0
        for p in personeller:
            gun_sayisi = int(teklif.get('gun_sayisi', 1))  # Teklif tablosundan gün sayısı
            gunluk_maas = float(p['gunluk_maas'])
            personel_toplam += gunluk_maas * gun_sayisi
        
        pdf.setFont("Helvetica", 11)
        pdf.drawString(50, y, f"Toplam Personel Maliyeti: {personel_toplam:,.2f} TL")
        y -= 20
    
    # Ürün listesi
    y -= 20
    if urunler:
        pdf.setFont("Helvetica-Bold", 12)
        pdf.drawString(40, y, "URUN LISTESI")
        y -= 20
        
        # Tablo başlığı
        pdf.setFont("Helvetica-Bold", 10)
        pdf.drawString(50, y, "Urun Adi")
        pdf.drawString(200, y, "Miktar")
        pdf.drawString(280, y, "Birim Fiyat")
        pdf.drawString(380, y, "KDV")
        pdf.drawString(450, y, "Toplam")
        pdf.line(40, y - 5, width - 40, y - 5)
        
        y -= 15
        pdf.setFont("Helvetica", 10)
        urun_toplam = 0
        for u in urunler:
            miktar = int(u['miktar'])
            birim_fiyat = float(u['birim_fiyat'])
            kdv_orani = float(u['kdv_orani'])
            kdv_yuzde = int(kdv_orani * 100)
            satirToplam = miktar * birim_fiyat * (1 + kdv_orani)
            urun_toplam += satirToplam
            
            pdf.drawString(50, y, temizle_turkce(u['ad']))
            pdf.drawString(200, y, str(miktar))
            pdf.drawString(280, y, f"{birim_fiyat:,.2f} TL")
            pdf.drawString(380, y, f"%{kdv_yuzde}")
            pdf.drawString(450, y, f"{satirToplam:,.2f} TL")
            y -= 15
    
    # Toplam fiyat kutusu - daha belirgin
    y -= 40
    toplam_fiyat = float(teklif['toplam_fiyat'])
    
    # Büyük toplam kutusu
    pdf.setFillGray(0.9)
    pdf.rect(width - 280, y - 60, 250, 60, fill=1)
    pdf.setFillGray(0)  # Siyaha geri döndür
    
    pdf.setFont("Helvetica-Bold", 14)
    pdf.drawString(width - 270, y - 20, "GENEL TOPLAM")
    pdf.setFont("Helvetica-Bold", 20)
    pdf.drawString(width - 270, y - 45, f"{toplam_fiyat:,.2f} TL")
    
    # Alt bilgi - daha profesyonel
    y -= 100
    pdf.setFillGray(0.95)
    pdf.rect(30, y - 40, width - 60, 40, fill=1)
    pdf.setFillGray(0)  # Siyaha geri döndür
    
    pdf.setFont("Helvetica-Bold", 10)
    pdf.drawString(40, y - 15, "NOTLAR VE KOSULLAR")
    pdf.setFont("Helvetica", 9)
    pdf.drawString(40, y - 28, "• Bu teklif 30 gun gecerlidir.")
    pdf.drawString(40, y - 38, "• Isbirligi icin tesekkur ederiz. - BYZDIZAYN INSAAT")
    
    # PDF'i kaydet
    pdf.save()
    buffer.seek(0)
    
    return send_file(buffer, as_attachment=True, download_name=f"teklif_{teklif_id}.pdf", mimetype='application/pdf')


if __name__ == '__main__':
    app.run(debug=True)