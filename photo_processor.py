from PIL import Image, ImageFilter, ImageEnhance, ImageOps
import io
from debug_utils import debug_print, log_call, DEBUG_MODE
import traceback
import random


@log_call
def convert_to_sketch(image_bytes):
    """Карандашный рисунок (улучшенный)"""
    debug_print(f"🔥 photo_processor: convert_to_sketch: ВЫЗВАНА")
    debug_print(f"📥 Аргументы: image_bytes размер={len(image_bytes)} байт")
    debug_print(f"🔥 photo_processor: convert_to_sketch: размер фото={len(image_bytes)} байт")
    debug_print(f"🔥 photo_processor: convert_to_sketch: конвертация в sketch...")

    try:
        img = Image.open(io.BytesIO(image_bytes)).convert('L')
        # Инвертируем
        inverted = ImageOps.invert(img)
        # Размытие
        blurred = inverted.filter(ImageFilter.GaussianBlur(radius=5))
        # Смешиваем
        final = ImageOps.invert(blurred)
        final_rgb = final.convert('RGB')
        # Немного повышаем контраст
        enhancer = ImageEnhance.Contrast(final_rgb)
        final_rgb = enhancer.enhance(1.2)
        output = io.BytesIO()
        final_rgb.save(output, format='JPEG')
        output.seek(0)
        debug_print(f"🔥 photo_processor: convert_to_sketch: результат сохранён")
        debug_print(f"🔥 photo_processor: convert_to_sketch: ВОЗВРАТ (размер={len(output.getvalue())} байт)")
        debug_print(f"🔥 photo_processor: convert_to_sketch: ВОЗВРАТ {output}")
        return output
    except Exception as e:
        debug_print(f"🔥 photo_processor: ОШИБКА: {e}")
        debug_print(f"🔥 photo_processor: traceback: {traceback.format_exc()}")
        raise


@log_call
def convert_to_anime(image_bytes):
    """Аниме-стиль: яркие цвета, резкость, насыщенность"""
    debug_print(f"🔥 photo_processor: convert_to_anime: ВЫЗВАНА")
    debug_print(f"📥 Аргументы: image_bytes размер={len(image_bytes)} байт")
    debug_print(f"🔥 photo_processor: convert_to_anime: конвертация в anime...")

    try:
        img = Image.open(io.BytesIO(image_bytes)).convert('RGB')
        # Повышаем контраст
        enhancer = ImageEnhance.Contrast(img)
        img = enhancer.enhance(1.5)
        # Повышаем насыщенность
        enhancer = ImageEnhance.Color(img)
        img = enhancer.enhance(1.4)
        # Резкость
        img = img.filter(ImageFilter.SHARPEN)
        img = img.filter(ImageFilter.SHARPEN)
        # Лёгкое свечение (размытие и наложение)
        blurred = img.filter(ImageFilter.GaussianBlur(radius=1))
        img = Image.blend(img, blurred, 0.2)
        output = io.BytesIO()
        img.save(output, format='JPEG')
        output.seek(0)
        debug_print(f"🔥 photo_processor: convert_to_anime: ВОЗВРАТ (размер={len(output.getvalue())} байт)")
        debug_print(f"🔥 photo_processor: convert_to_anime: ВОЗВРАТ {output}")
        return output
    except Exception as e:
        debug_print(f"🔥 photo_processor: ОШИБКА: {e}")
        debug_print(f"🔥 photo_processor: traceback: {traceback.format_exc()}")
        raise


@log_call
def convert_to_sepia(image_bytes):
    """Сепия (усиленная)"""
    debug_print(f"🔥 photo_processor: convert_to_sepia: ВЫЗВАНА")
    debug_print(f"📥 Аргументы: image_bytes размер={len(image_bytes)} байт")
    debug_print(f"🔥 photo_processor: convert_to_sepia: конвертация в sepia...")

    try:
        img = Image.open(io.BytesIO(image_bytes)).convert('RGB')
        sepia = (0.393, 0.769, 0.189, 0,
                 0.349, 0.686, 0.168, 0,
                 0.272, 0.534, 0.131, 0)
        img = img.convert('RGB', matrix=sepia)
        # Немного добавляем яркости
        enhancer = ImageEnhance.Brightness(img)
        img = enhancer.enhance(1.1)
        output = io.BytesIO()
        img.save(output, format='JPEG')
        output.seek(0)
        debug_print(f"🔥 photo_processor: convert_to_sepia: ВОЗВРАТ (размер={len(output.getvalue())} байт)")
        debug_print(f"🔥 photo_processor: convert_to_sepia: ВОЗВРАТ {output}")
        return output
    except Exception as e:
        debug_print(f"🔥 photo_processor: ОШИБКА: {e}")
        debug_print(f"🔥 photo_processor: traceback: {traceback.format_exc()}")
        raise


@log_call
def convert_to_hard_rock(image_bytes):
    """Хард-рок: высокий контраст, резкость, зернистость"""
    debug_print(f"🔥 photo_processor: convert_to_hard_rock: ВЫЗВАНА")
    debug_print(f"📥 Аргументы: image_bytes размер={len(image_bytes)} байт")
    debug_print(f"🔥 photo_processor: convert_to_hard_rock: конвертация в hard_rock...")

    try:
        img = Image.open(io.BytesIO(image_bytes)).convert('RGB')
        enhancer = ImageEnhance.Contrast(img)
        img = enhancer.enhance(2.2)
        enhancer = ImageEnhance.Sharpness(img)
        img = enhancer.enhance(3.5)
        # Добавляем лёгкое зерно (шум)
        noise = Image.new('RGB', img.size, (0, 0, 0))
        noise_pixels = noise.load()
        for x in range(img.size[0]):
            for y in range(img.size[1]):
                r = random.randint(0, 20)
                noise_pixels[x, y] = (r, r, r)
        img = Image.blend(img, noise, 0.1)
        output = io.BytesIO()
        img.save(output, format='JPEG')
        output.seek(0)
        debug_print(f"🔥 photo_processor: convert_to_hard_rock: ВОЗВРАТ (размер={len(output.getvalue())} байт)")
        debug_print(f"🔥 photo_processor: convert_to_hard_rock: ВОЗВРАТ {output}")
        return output
    except Exception as e:
        debug_print(f"🔥 photo_processor: ОШИБКА: {e}")
        debug_print(f"🔥 photo_processor: traceback: {traceback.format_exc()}")
        raise


@log_call
def convert_to_pixel(image_bytes, pixel_size=15):
    """Пикселизация (более выраженная)"""
    debug_print(f"🔥 photo_processor: convert_to_pixel: ВЫЗВАНА")
    debug_print(f"📥 Аргументы: image_bytes размер={len(image_bytes)} байт")
    debug_print(f"🔥 photo_processor: convert_to_pixel: конвертация в pixel...")

    try:
        img = Image.open(io.BytesIO(image_bytes)).convert('RGB')
        img_small = img.resize((img.width // pixel_size, img.height // pixel_size), Image.NEAREST)
        img_pixel = img_small.resize(img.size, Image.NEAREST)
        output = io.BytesIO()
        img_pixel.save(output, format='JPEG')
        output.seek(0)
        debug_print(f"🔥 photo_processor: convert_to_pixel: ВОЗВРАТ (размер={len(output.getvalue())} байт)")
        debug_print(f"🔥 photo_processor: convert_to_pixel: ВОЗВРАТ {output}")
        return output
    except Exception as e:
        debug_print(f"🔥 photo_processor: ОШИБКА: {e}")
        debug_print(f"🔥 photo_processor: traceback: {traceback.format_exc()}")
        raise


@log_call
def convert_to_neon(image_bytes):
    """Неоновые цвета: сильная насыщенность, контраст, свечение"""
    debug_print(f"🔥 photo_processor: convert_to_neon: ВЫЗВАНА")
    debug_print(f"📥 Аргументы: image_bytes размер={len(image_bytes)} байт")
    debug_print(f"🔥 photo_processor: convert_to_neon: конвертация в neon...")

    try:
        img = Image.open(io.BytesIO(image_bytes)).convert('RGB')
        enhancer = ImageEnhance.Color(img)
        img = enhancer.enhance(3.0)
        enhancer = ImageEnhance.Contrast(img)
        img = enhancer.enhance(1.8)
        # Добавляем свечение
        blurred = img.filter(ImageFilter.GaussianBlur(radius=3))
        img = Image.blend(img, blurred, 0.4)
        output = io.BytesIO()
        img.save(output, format='JPEG')
        output.seek(0)
        debug_print(f"🔥 photo_processor: convert_to_neon: ВОЗВРАТ (размер={len(output.getvalue())} байт)")
        debug_print(f"🔥 photo_processor: convert_to_neon: ВОЗВРАТ {output}")
        return output
    except Exception as e:
        debug_print(f"🔥 photo_processor: ОШИБКА: {e}")
        debug_print(f"🔥 photo_processor: traceback: {traceback.format_exc()}")
        raise


@log_call
def convert_to_oil(image_bytes):
    """Масляная живопись (через ModeFilter и шум)"""
    debug_print(f"🔥 photo_processor: convert_to_oil: ВЫЗВАНА")
    debug_print(f"📥 Аргументы: image_bytes размер={len(image_bytes)} байт")
    debug_print(f"🔥 photo_processor: convert_to_oil: конвертация в oil...")

    try:
        img = Image.open(io.BytesIO(image_bytes)).convert('RGB')
        # Увеличиваем размер для лучшего эффекта
        img = img.resize((img.width * 2, img.height * 2), Image.BICUBIC)
        # Применяем ModeFilter
        img = img.filter(ImageFilter.ModeFilter(size=7))
        # Возвращаем к исходному размеру
        img = img.resize((img.width // 2, img.height // 2), Image.BICUBIC)
        # Добавляем лёгкое размытие
        img = img.filter(ImageFilter.GaussianBlur(radius=1))
        output = io.BytesIO()
        img.save(output, format='JPEG')
        output.seek(0)
        debug_print(f"🔥 photo_processor: convert_to_oil: ВОЗВРАТ (размер={len(output.getvalue())} байт)")
        debug_print(f"🔥 photo_processor: convert_to_oil: ВОЗВРАТ {output}")
        return output
    except Exception as e:
        debug_print(f"🔥 photo_processor: ОШИБКА: {e}")
        debug_print(f"🔥 photo_processor: traceback: {traceback.format_exc()}")
        raise


@log_call
def convert_to_watercolor(image_bytes):
    """Акварель: мягкие цвета, пастель"""
    debug_print(f"🔥 photo_processor: convert_to_watercolor: ВЫЗВАНА")
    debug_print(f"📥 Аргументы: image_bytes размер={len(image_bytes)} байт")
    debug_print(f"🔥 photo_processor: convert_to_watercolor: конвертация в watercolor...")

    try:
        img = Image.open(io.BytesIO(image_bytes)).convert('RGB')
        # Размытие
        img = img.filter(ImageFilter.GaussianBlur(radius=2))
        # Уменьшаем насыщенность
        enhancer = ImageEnhance.Color(img)
        img = enhancer.enhance(0.7)
        # Повышаем яркость
        enhancer = ImageEnhance.Brightness(img)
        img = enhancer.enhance(1.1)
        output = io.BytesIO()
        img.save(output, format='JPEG')
        output.seek(0)
        debug_print(f"🔥 photo_processor: convert_to_watercolor: ВОЗВРАТ (размер={len(output.getvalue())} байт)")
        debug_print(f"🔥 photo_processor: convert_to_watercolor: ВОЗВРАТ {output}")
        return output
    except Exception as e:
        debug_print(f"🔥 photo_processor: ОШИБКА: {e}")
        debug_print(f"🔥 photo_processor: traceback: {traceback.format_exc()}")
        raise


@log_call
def convert_to_cartoon(image_bytes):
    """Мультяшный: яркие цвета, чёткие края, высокая резкость"""
    debug_print(f"🔥 photo_processor: convert_to_cartoon: ВЫЗВАНА")
    debug_print(f"📥 Аргументы: image_bytes размер={len(image_bytes)} байт")
    debug_print(f"🔥 photo_processor: convert_to_cartoon: конвертация в cartoon...")

    try:
        img = Image.open(io.BytesIO(image_bytes)).convert('RGB')
        # Сильное повышение контраста
        enhancer = ImageEnhance.Contrast(img)
        img = enhancer.enhance(2.2)
        # Сильное повышение цвета
        enhancer = ImageEnhance.Color(img)
        img = enhancer.enhance(2.2)
        # Резкость
        img = img.filter(ImageFilter.SHARPEN)
        img = img.filter(ImageFilter.SHARPEN)
        img = img.filter(ImageFilter.SHARPEN)
        # Выделение краёв (лайны)
        edges = img.filter(ImageFilter.FIND_EDGES)
        edges = edges.convert('L')
        edges = edges.point(lambda x: 0 if x < 100 else 255)
        # Накладываем края на исходное изображение
        img = Image.blend(img, edges.convert('RGB'), 0.2)
        output = io.BytesIO()
        img.save(output, format='JPEG')
        output.seek(0)
        debug_print(f"🔥 photo_processor: convert_to_cartoon: ВОЗВРАТ (размер={len(output.getvalue())} байт)")
        debug_print(f"🔥 photo_processor: convert_to_cartoon: ВОЗВРАТ {output}")
        return output
    except Exception as e:
        debug_print(f"🔥 photo_processor: ОШИБКА: {e}")
        debug_print(f"🔥 photo_processor: traceback: {traceback.format_exc()}")
        raise


def process_photo(image_bytes, effect):
    """Общая функция-обработчик"""
    if DEBUG_MODE:
        debug_print(f"🔥 photo_processor: process_photo: effect={effect}")
        debug_print(f"🔥 photo_processor: process_photo: размер фото={len(image_bytes)} байт")
        debug_print(f"🔥 photo_processor: process_photo: вызов функции {effect}")

    effects = {
        'sketch': convert_to_sketch,
        'anime': convert_to_anime,
        'sepia': convert_to_sepia,
        'hard_rock': convert_to_hard_rock,
        'pixel': convert_to_pixel,
        'neon': convert_to_neon,
        'oil': convert_to_oil,
        'watercolor': convert_to_watercolor,
        'cartoon': convert_to_cartoon,
    }

    try:
        result = effects[effect](image_bytes)
        if DEBUG_MODE:
            debug_print(f"🔥 photo_processor: process_photo: ВОЗВРАТ")
        return result
    except KeyError as e:
        debug_print(f"🔥 photo_processor: ОШИБКА: Неизвестный эффект {effect}")
        debug_print(f"🔥 photo_processor: traceback: {traceback.format_exc()}")
        raise ValueError(f"Unknown effect: {effect}")
    except Exception as e:
        debug_print(f"🔥 photo_processor: ОШИБКА: {e}")
        debug_print(f"🔥 photo_processor: traceback: {traceback.format_exc()}")
        raise