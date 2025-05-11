from mnemosyne import config, utils

def test_env_loading():
    print("Testing environment variable loading...")
    print(f"NEO4J_URI: {config.NEO4J_URI}")
    print(f"NEO4J_USER: {config.NEO4J_USER}")
    print(f"LLM_MODEL: {config.LLM_MODEL}")
    print(f"DATA_FOLDER: {config.DATA_FOLDER}")
    print("✅ Environment variables loaded successfully.")

def test_utils_clean_text():
    print("Testing text cleaning utility...")
    messy_text = "This   is    a test.\n\n With   extra spaces!"
    cleaned = utils.clean_text(messy_text)
    assert cleaned == "This is a test. With extra spaces!", "Text cleaning failed"
    print("✅ Text cleaning works as expected.")

if __name__ == "__main__":
    test_env_loading()
    test_utils_clean_text()