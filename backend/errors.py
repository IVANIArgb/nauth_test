import traceback
from flask import Flask, jsonify, request
from werkzeug.exceptions import HTTPException


def register_error_handlers(app: Flask) -> None:
    @app.errorhandler(404)
    def not_found(e):
        return jsonify({"error": "Not Found", "message": "Page not found"}), 404

    @app.errorhandler(500)
    def internal_error(e):
        response = {"error": "Internal Server Error", "message": "Something went wrong"}
        if app.config.get("TESTING"):
            response["traceback"] = traceback.format_exc()
        return jsonify(response), 500

    @app.errorhandler(Exception)
    def handle_exception(e):
        if isinstance(e, HTTPException):
            return jsonify({"error": e.name, "message": e.description}), e.code
        
        app.logger.exception("Unhandled Exception")
        # В production не возвращаем детали ошибки пользователю
        if app.config.get("TESTING") or app.config.get("DEBUG"):
            return jsonify({"error": "Internal Server Error", "message": str(e)}), 500
        else:
            return jsonify({"error": "Internal Server Error", "message": "An error occurred. Please contact support."}), 500

