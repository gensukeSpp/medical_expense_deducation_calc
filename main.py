def main():
    # 引数解析と初期化
    from app.args import setup_args, setup_directories

    args = setup_args()
    input_dir, output_dir, processed_dir, failed_dir = setup_directories(args)

    # OCRエンジン初期化
    from paddleocr import PaddleOCR

    ocr = PaddleOCR(use_angle_cls=True, lang="japan", enable_mkldnn=False)

    # Watcherの起動
    from app import watcher

    if args.watch:
        # Start watcher (either watchdog observer or polling loop)
        if args.use_watchdog:
            print("Starting watcher (watchdog mode)...")
            watcher.run_watchdog(
                input_dir,
                output_dir,
                processed_dir,
                failed_dir,
                poll_interval=args.poll_interval,
                retries=args.retries,
            )
        else:
            print("Starting watcher (polling mode)...")
            watcher.run_loop(
                input_dir,
                output_dir,
                processed_dir,
                failed_dir,
                poll_interval=args.poll_interval,
                run_once=False,
                retries=args.retries,
            )
        return

    # If an OCR JSON is provided, process it to structured output
    if args.input_json:
        from app.structural_parser import process_input_json

        structured = process_input_json(args.input_json, model=args.model, output_dir=args.output_dir)
        if structured is None:
            print(f"Failed to process input JSON: {args.input_json}")
        else:
            print(f"Structured data written for {args.input_json}")
        return

    # 単一画像の処理
    from app.processor import process_single_image

    process_single_image(args, input_dir, output_dir, ocr)


if __name__ == "__main__":
    main()
