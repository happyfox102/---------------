import unittest
from friday.speech import speech_text, Listener


class SpeechCleanTests(unittest.TestCase):
    def test_speaker_removes_emoji_and_markup(self):
        self.assertEqual(speech_text('Готово ✅ **Открыла** папку 🚀'), 'Готово Открыла папку')

    def test_recognition_variants_are_canonicalized(self):
        self.assertEqual(Listener.command_cleanup('Пятница, открой папочку код'), 'открой папку код')
        self.assertEqual(Listener.command_cleanup('сделай снимок экрана'), 'сделай скриншот')
        self.assertEqual(Listener.command_cleanup('включи энергосбережения'), 'включи энергосбережение')


if __name__ == '__main__': unittest.main()
