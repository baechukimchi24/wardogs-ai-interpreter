"""Optional offline English -> Korean Argos model installer (run from app venv)."""
import sys


def main():
    import argostranslate.package
    from argostranslate.translate import get_installed_languages
    langs = get_installed_languages()
    for lang in langs:
        if lang.code == "en" and any(x.code == "ko" for x in langs if x != lang):
            try:
                from argostranslate.translate import translate
                print("Checking installed pair:", translate("Hello there!", "en", "ko"))
                return
            except Exception:
                break
    print("Retrieving Argos translation package index…")
    argostranslate.package.update_package_index()
    pairs = [p for p in argostranslate.package.get_available_packages()
             if p.from_code == "en" and p.to_code == "ko"]
    if not pairs:
        raise SystemExit("en→ko model not in current Argos index. Choose Google/OpenAI instead.")
    path = pairs[0].download()
    argostranslate.package.install_from_path(path)
    print("English to Korean offline model installed.")


if __name__ == "__main__":
    main()
