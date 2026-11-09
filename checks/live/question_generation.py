def main():
    # Uses the same uploaded-file path and question API as the browser.
    from checks.live.question_endpoint import main as run
    run()


if __name__ == '__main__':
    main()
