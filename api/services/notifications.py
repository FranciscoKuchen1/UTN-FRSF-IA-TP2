from abc import ABC, abstractmethod


class NotificationService(ABC):
    """
    Interfaz abstracta para servicios de notificación (SOLID: Dependency Inversion).
    """

    @abstractmethod
    def send_response(self, user_id: str, message: str) -> bool:
        """
        Envía un mensaje de respuesta a un usuario.
        
        Args:
            user_id: ID del usuario (UUID de Supabase).
            message: Contenido del mensaje a enviar.
            
        Returns:
            bool: True si se envió correctamente, False en caso contrario.
        """
        pass


class ConsoleNotificationService(NotificationService):
    """
    Implementación temporal que simula el envío imprimiendo en consola.
    """

    def send_response(self, user_id: str, message: str) -> bool:
        print("\n" + "="*50)
        print(f"📧 [NOTIFICACIÓN ENVIADA AL CLIENTE {user_id}]")
        print(f"Mensaje: {message}")
        print("="*50 + "\n")
        return True
