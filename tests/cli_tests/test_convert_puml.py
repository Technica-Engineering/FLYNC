"""Tests for flync_cli.convert_puml."""

from unittest.mock import MagicMock, patch

import pytest

from flync_cli.convert_puml import convert_puml, download_jar, main, wrap_svg_in_html


class TestDownloadJar:
    def test_success_writes_file(self, tmp_path):
        jar_path = tmp_path / "plantuml.jar"
        mock_ctx = MagicMock()
        mock_ctx.__enter__ = lambda s: s
        mock_ctx.__exit__ = MagicMock(return_value=False)
        mock_ctx.read.return_value = b"fake-jar-bytes"

        with patch("urllib.request.urlopen", return_value=mock_ctx):
            result = download_jar(jar_path)

        assert result is True
        assert jar_path.read_bytes() == b"fake-jar-bytes"

    def test_network_error_returns_false(self, tmp_path, capsys):
        jar_path = tmp_path / "plantuml.jar"
        with patch("urllib.request.urlopen", side_effect=OSError("connection refused")):
            result = download_jar(jar_path)
        assert result is False
        assert "Error" in capsys.readouterr().out


class TestWrapSvgInHtml:
    def test_creates_html_file(self, tmp_path):
        svg_path = tmp_path / "diagram.svg"
        svg_path.write_text('<svg xmlns="http://www.w3.org/2000/svg"><rect/></svg>')

        wrap_svg_in_html(svg_path)

        html_path = tmp_path / "diagram.html"
        assert html_path.exists()
        content = html_path.read_text(encoding="utf-8")
        assert "<!DOCTYPE html>" in content
        assert "<svg" in content
        assert "FLYNC Architecture Explorer" in content
        assert "diagram.svg" in content

    def test_svg_content_embedded(self, tmp_path):
        svg_path = tmp_path / "test.svg"
        svg_path.write_text('<svg xmlns="http://www.w3.org/2000/svg"><circle r="50"/></svg>')

        wrap_svg_in_html(svg_path)

        html = (tmp_path / "test.html").read_text(encoding="utf-8")
        assert "<circle" in html

    def test_zoom_controls_present(self, tmp_path):
        svg_path = tmp_path / "z.svg"
        svg_path.write_text("<svg/>")

        wrap_svg_in_html(svg_path)

        html = (tmp_path / "z.html").read_text(encoding="utf-8")
        assert "changeZoom" in html
        assert "resetZoom" in html


class TestConvertPuml:
    def test_missing_input_returns_false(self, tmp_path, capsys):
        result = convert_puml(str(tmp_path / "nonexistent.puml"), "html")
        assert result is False
        assert "does not exist" in capsys.readouterr().out

    def test_jar_download_failure_returns_false(self, tmp_path, monkeypatch, capsys):
        monkeypatch.chdir(tmp_path)
        puml = tmp_path / "test.puml"
        puml.write_text("@startuml\n@enduml")
        with patch("flync_cli.convert_puml.download_jar", return_value=False):
            result = convert_puml(str(puml), "html")
        assert result is False
        assert "plantuml.jar" in capsys.readouterr().out

    def test_subprocess_error_returns_false(self, tmp_path, monkeypatch, capsys):
        monkeypatch.chdir(tmp_path)
        puml = tmp_path / "test.puml"
        puml.write_text("@startuml\n@enduml")
        (tmp_path / "plantuml.jar").write_bytes(b"fake")
        proc = MagicMock()
        proc.returncode = 1
        proc.stderr = "syntax error"
        with patch("subprocess.run", return_value=proc):
            result = convert_puml(str(puml), "html")
        assert result is False
        assert "PlantUML Error" in capsys.readouterr().out

    def test_html_conversion_success(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        puml = tmp_path / "test.puml"
        puml.write_text("@startuml\n@enduml")
        (tmp_path / "plantuml.jar").write_bytes(b"fake")
        (tmp_path / "test.svg").write_text('<svg xmlns="http://www.w3.org/2000/svg"/>')
        proc = MagicMock()
        proc.returncode = 0
        with patch("subprocess.run", return_value=proc):
            result = convert_puml(str(puml), "html")
        assert result is True
        assert (tmp_path / "test.html").exists()

    def test_html_svg_missing_returns_false(self, tmp_path, monkeypatch, capsys):
        monkeypatch.chdir(tmp_path)
        puml = tmp_path / "test.puml"
        puml.write_text("@startuml\n@enduml")
        (tmp_path / "plantuml.jar").write_bytes(b"fake")
        proc = MagicMock()
        proc.returncode = 0
        with patch("subprocess.run", return_value=proc):
            result = convert_puml(str(puml), "html")
        assert result is False
        assert "SVG generation failed" in capsys.readouterr().out

    def test_pdf_uses_tpdf_flag(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        puml = tmp_path / "test.puml"
        puml.write_text("@startuml\n@enduml")
        (tmp_path / "plantuml.jar").write_bytes(b"fake")
        proc = MagicMock()
        proc.returncode = 0
        with patch("subprocess.run", return_value=proc) as mock_run:
            result = convert_puml(str(puml), "pdf")
        assert result is True
        assert "-tpdf" in mock_run.call_args[0][0]

    def test_svg_uses_tsvg_flag(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        puml = tmp_path / "test.puml"
        puml.write_text("@startuml\n@enduml")
        (tmp_path / "plantuml.jar").write_bytes(b"fake")
        proc = MagicMock()
        proc.returncode = 0
        with patch("subprocess.run", return_value=proc) as mock_run:
            result = convert_puml(str(puml), "svg")
        assert result is True
        assert "-tsvg" in mock_run.call_args[0][0]

    def test_png_uses_tpng_flag(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        puml = tmp_path / "test.puml"
        puml.write_text("@startuml\n@enduml")
        (tmp_path / "plantuml.jar").write_bytes(b"fake")
        proc = MagicMock()
        proc.returncode = 0
        with patch("subprocess.run", return_value=proc) as mock_run:
            result = convert_puml(str(puml), "png")
        assert result is True
        assert "-tpng" in mock_run.call_args[0][0]

    def test_exception_in_subprocess_returns_false(self, tmp_path, monkeypatch, capsys):
        monkeypatch.chdir(tmp_path)
        puml = tmp_path / "test.puml"
        puml.write_text("@startuml\n@enduml")
        (tmp_path / "plantuml.jar").write_bytes(b"fake")
        with patch("subprocess.run", side_effect=RuntimeError("java not found")):
            result = convert_puml(str(puml), "png")
        assert result is False
        assert "occurred" in capsys.readouterr().out

    def test_jar_already_present_skips_download(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        puml = tmp_path / "test.puml"
        puml.write_text("@startuml\n@enduml")
        (tmp_path / "plantuml.jar").write_bytes(b"existing-jar")
        proc = MagicMock()
        proc.returncode = 0
        with (
            patch("subprocess.run", return_value=proc),
            patch("flync_cli.convert_puml.download_jar") as mock_dl,
        ):
            convert_puml(str(puml), "png")
        mock_dl.assert_not_called()


class TestMain:
    def test_success_exits_0(self, monkeypatch):
        monkeypatch.setattr("sys.argv", ["puml-to-html", "test.puml"])
        with patch("flync_cli.convert_puml.convert_puml", return_value=True):
            with pytest.raises(SystemExit) as exc:
                main()
        assert exc.value.code == 0

    def test_failure_exits_1(self, monkeypatch):
        monkeypatch.setattr("sys.argv", ["puml-to-html", "test.puml"])
        with patch("flync_cli.convert_puml.convert_puml", return_value=False):
            with pytest.raises(SystemExit) as exc:
                main()
        assert exc.value.code == 1

    def test_format_flag_passed_through(self, monkeypatch):
        monkeypatch.setattr("sys.argv", ["puml-to-html", "test.puml", "--format", "svg"])
        with patch("flync_cli.convert_puml.convert_puml", return_value=True) as mock_convert:
            with pytest.raises(SystemExit):
                main()
        assert mock_convert.call_args[0][1] == "svg"
