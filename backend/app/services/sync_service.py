import logging
from sqlalchemy.orm import Session
from app.models import ClientKey, Node, ProtocolType
from app.services.amnezia import AmneziaClient
from app.config import settings

logger = logging.getLogger("b2b_sync")

async def sync_remote_amnezia_keys(db: Session):
    """
    Synchronizes ClientKey records with amneziavpnphp.
    If a key was manually deleted in amneziavpnphp, removes it from B2B Orchestrator DB.
    """
    awg_nodes = db.query(Node).filter(Node.node_type == "amnezia").all()
    
    for node in awg_nodes:
        if not node.amnezia_server_id:
            continue
        try:
            amnezia_target_url = node.amnezia_url or settings.AMNEZIA_API_URL
            amnezia = AmneziaClient(amnezia_target_url, settings.AMNEZIA_ADMIN_EMAIL, settings.AMNEZIA_ADMIN_PASSWORD)
            remote_res = await amnezia.list_server_clients(node.amnezia_server_id)
            
            if not remote_res.get("success"):
                continue

            remote_clients = remote_res.get("clients", [])
            active_remote_ids = {str(c["id"]) for c in remote_clients}

            local_keys = db.query(ClientKey).filter(
                ClientKey.node_id == node.id,
                ClientKey.protocol == ProtocolType.AMNEZIA_WG
            ).all()

            for k in local_keys:
                if k.remote_client_id and k.remote_client_id not in active_remote_ids:
                    logger.info(f"Key ID {k.id} ({k.employee_name}) was deleted in amneziavpnphp. Removing from B2B Orchestrator DB.")
                    db.delete(k)

            db.commit()
        except Exception as e:
            logger.error(f"Error syncing Amnezia node {node.id}: {e}")
