from meeting_recorder.cli import build_parser


def test_parser_description_and_new_commands():
    parser = build_parser()
    help_text = parser.format_help()
    assert "Local-first Linux meeting recorder" in help_text
    for command in ["doctor", "status", "list", "show", "open"]:
        assert command in help_text


def test_doctor_parser_accepts_json_and_check():
    args = build_parser().parse_args(["doctor", "--json", "--check", "ffmpeg"])
    assert args.command == "doctor"
    assert args.json is True
    assert args.check == ["ffmpeg"]


def test_record_parser_accepts_reliability_options():
    args = build_parser().parse_args(["record", "--display", ":1", "--no-summary", "--open", "--json", "--size", "1280x720"])
    assert args.display == ":1"
    assert args.no_summary is True
    assert args.open is True
    assert args.json is True
    assert args.size == "1280x720"


def test_library_parsers():
    args = build_parser().parse_args(["list", "--limit", "5", "--json"])
    assert args.limit == 5
    assert args.json is True
    args = build_parser().parse_args(["show", "abc", "--json"])
    assert args.meeting == "abc"
    assert args.json is True
    args = build_parser().parse_args(["open", "abc", "--target", "summary"])
    assert args.target == "summary"
