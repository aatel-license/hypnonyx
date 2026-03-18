#!/usr/bin/env python3
"""
Message Broker con fallback in-memory FUNZIONANTE
Fix: gestione corretta della coda e delivery dei messaggi (Pub/Sub Broadcast)
Fix: timeout su connessioni esterne (Kafka/MQTT)
"""

import asyncio
import logging
from typing import Dict, Callable, Any, Optional
from collections import defaultdict
import json

from config import USE_MQTT, USE_KAFKA, MQTT_BROKER, MQTT_PORT, KAFKA_BOOTSTRAP_SERVERS

try:
    import aiomqtt
except ImportError:
    aiomqtt = None

try:
    import aiokafka
except ImportError:
    aiokafka = None

logger = logging.getLogger(__name__)


class MessageBroker:
    """Message broker con fallback in-memory che FUNZIONA (Fix Pub/Sub)"""

    # CRITICAL FIX: Handlers condivisi per in-memory Pub/Sub
    # Usiamo una lista di handler per ogni topic
    _in_memory_handlers: Dict[str, list] = defaultdict(list)

    # Lock per gestione concorrente della registrazione handler
    _handler_lock = asyncio.Lock()

    def __init__(self, agent_id: str, project_id: str = "default_project"):
        self.agent_id = agent_id
        self.agent_type = None  # Will be set by BaseAgent
        self.running = False
        self.project_id = project_id  # ← aggiunto
        # Flags configurazione
        self.use_mqtt = USE_MQTT
        self.use_kafka = USE_KAFKA

        # Clients
        self._mqtt_client = None
        self._kafka_producer = None
        self._kafka_consumer = None

        logger.info(
            f"MessageBroker initialized for {agent_id} (Config: MQTT={self.use_mqtt}, Kafka={self.use_kafka})"
        )

    async def connect(self):
        """Connette al broker configurato"""
        self.running = True

        # Tentativo connessione MQTT
        if self.use_mqtt:
            if aiomqtt:
                try:
                    self._mqtt_client = aiomqtt.Client(MQTT_BROKER, port=MQTT_PORT)
                    # Task per loop MQTT
                    asyncio.create_task(self._mqtt_loop())
                    logger.info(
                        f"✓ MQTT listener avviato per {self.agent_id} su {MQTT_BROKER}:{MQTT_PORT}"
                    )
                except Exception as e:
                    logger.error(f"Errore inizializzazione MQTT: {e}")
                    self.use_mqtt = False
            else:
                logger.error("ERRORE: USE_MQTT=true ma 'aiomqtt' non è installato.")
                self.use_mqtt = False

        # Tentativo connessione Kafka
        if self.use_kafka:
            if aiokafka:
                try:
                    from aiokafka import AIOKafkaProducer
                    from aiokafka.admin import AIOKafkaAdminClient, NewTopic
                    from config import get_topics

                    # 1. Ensure topics exist (Admin check)
                    try:
                        admin = AIOKafkaAdminClient(
                            bootstrap_servers=KAFKA_BOOTSTRAP_SERVERS
                        )
                        await asyncio.wait_for(admin.start(), timeout=5.0)

                        existing_topics = await admin.list_topics()
                        new_topics = []
                        for topic in get_topics(self.project_id).values():
                            if topic not in existing_topics:
                                logger.info(
                                    f"Kafka: topic '{topic}' non trovato. Creazione in corso..."
                                )
                                new_topics.append(
                                    NewTopic(
                                        name=topic,
                                        num_partitions=1,
                                        replication_factor=1,
                                    )
                                )

                        if new_topics:
                            await admin.create_topics(new_topics)
                            logger.info(
                                f"✓ Creati {len(new_topics)} nuovi topic Kafka."
                            )

                        await admin.close()
                    except Exception as admin_err:
                        logger.warning(
                            f"Kafka Admin non disponibile (Topic auto-creation saltata): {admin_err}"
                        )

                    # 2. Start Producer
                    self._kafka_producer = AIOKafkaProducer(
                        bootstrap_servers=KAFKA_BOOTSTRAP_SERVERS
                    )

                    # FIX: Timeout per evitare hang se Kafka non è raggiungibile
                    try:
                        await asyncio.wait_for(
                            self._kafka_producer.start(), timeout=5.0
                        )
                        logger.info(
                            f"✓ Kafka Producer connesso a {KAFKA_BOOTSTRAP_SERVERS}"
                        )
                    except asyncio.TimeoutError:
                        logger.error(
                            f"Timeout connessione Kafka ({KAFKA_BOOTSTRAP_SERVERS}). Disabilitando Kafka."
                        )
                        self.use_kafka = False
                    except Exception as e:
                        # Gestisci altri errori di connessione
                        logger.error(f"Errore connessione Kafka: {e}")
                        self.use_kafka = False

                except Exception as e:
                    logger.error(f"Errore inizializzazione Kafka: {e}")
                    self.use_kafka = False
            else:
                logger.error("ERRORE: USE_KAFKA=true ma 'aiokafka' non è installato.")
                self.use_kafka = False

        if not self.use_mqtt and not self.use_kafka:
            logger.info(
                "Nessun broker esterno (MQTT/Kafka) configurato o raggiungibile. Utilizzo sistema di comunicazione in-memory."
            )

        return True

    async def subscribe(self, topic: str, handler: Callable):
        """Sottoscrive a un topic"""
        # Sottoscrizione in-memory (sempre attiva come fallback/primary)
        async with self._handler_lock:
            self._in_memory_handlers[topic].append(handler)

        if self.use_mqtt and self._mqtt_client and aiomqtt:
            # MQTT richiede di essere nel loop di ricezione.
            # Qui logghiamo solo, la sottoscrizione reale è nel loop
            logger.info(f"Agent {self.agent_id}: sottoscritto a MQTT topic {topic}")

        elif self.use_kafka and self._kafka_producer:
            logger.info(f"Agent {self.agent_id}: sottoscritto a Kafka topic {topic}")
            asyncio.create_task(self._kafka_consume_loop(topic))
        else:
            logger.info(
                f"Agent {self.agent_id}: sottoscritto a in-memory topic {topic}"
            )

    async def publish(self, topic: str, message: Dict[str, Any]):
        """Pubblica un messaggio"""
        if not isinstance(message, dict):
            logger.error(f"Message must be dict, got {type(message)}")
            return

        message_copy = json.loads(json.dumps(message, default=str))  # Deep copy
        payload = json.dumps(message_copy)

        # 1. Publish In-Memory (Broadcast immediato)
        # Copia handlers per thread safety durante iterazione
        handlers = []
        async with self._handler_lock:
            handlers = self._in_memory_handlers.get(topic, [])[:]

        if handlers:
            for handler in handlers:
                try:
                    # Esegue l'handler in un task separato per non bloccare
                    if asyncio.iscoroutinefunction(handler):
                        asyncio.create_task(handler(message_copy))
                    else:
                        asyncio.get_event_loop().call_soon(handler, message_copy)
                except Exception as e:
                    logger.error(f"Error dispatching in-memory message to handler: {e}")

        # 2. Publish MQTT
        if self.use_mqtt and self._mqtt_client and aiomqtt:
            try:
                # Nota: aiomqtt richiede di usare il context manager o essere in loop
                # Questa implementazione è semplificata e potrebbe richiedere lock se self._mqtt_client non è thread-safe in questo modo
                # Idealmente dovremmo accodare. Per ora proviamo direct publish.
                # WARNING: aiomqtt client usage outside context manager might be tricky.
                # Assuming single threaded asyncio loop, it might work if client is connected.
                pass
                # TODO: Implement MQTT publish properly if needed.
            except Exception as e:
                logger.error(f"Errore publish MQTT: {e}")

        # 3. Publish Kafka
        if self.use_kafka and self._kafka_producer:
            try:
                await self._kafka_producer.send_and_wait(topic, payload.encode("utf-8"))
            except Exception as e:
                logger.error(f"Errore publish Kafka su {topic}: {e}")

        logger.debug(f"Published to {topic}: {message_copy.get('task_id', 'no-id')}")

    async def _mqtt_loop(self):
        """Gestisce la ricezione messaggi MQTT"""
        try:
            import aiomqtt

            async with aiomqtt.Client(MQTT_BROKER, port=MQTT_PORT) as client:
                await client.subscribe("#")
                async for message in client.messages:
                    topic = str(message.topic)
                    try:
                        data = json.loads(message.payload.decode())
                        # In questo caso, invochiamo gli handler registrati
                        handlers = []
                        async with self._handler_lock:
                            handlers = self._in_memory_handlers.get(topic, [])[:]

                        for handler in handlers:
                            asyncio.create_task(handler(data))
                    except Exception as e:
                        logger.error(f"MQTT process error: {e}")
        except Exception as e:
            if self.running:
                logger.error(f"MQTT Loop failed: {e}")

    async def _kafka_consume_loop(self, topic: str):
        """Gestisce la ricezione messaggi Kafka"""
        try:
            from aiokafka import AIOKafkaConsumer

            consumer = AIOKafkaConsumer(
                topic,
                bootstrap_servers=KAFKA_BOOTSTRAP_SERVERS,
                group_id=f"group_{self.agent_id}",
                auto_offset_reset="latest",  # ← ignora messaggi vecchi, legge solo nuovi
                metadata_max_age_ms=5000,
            )
            await consumer.start()
            try:
                async for msg in consumer:
                    try:
                        data = json.loads(msg.value.decode("utf-8"))
                        handlers = []
                        async with self._handler_lock:
                            handlers = self._in_memory_handlers.get(topic, [])[:]

                        for handler in handlers:
                            asyncio.create_task(handler(data))
                    except Exception as e:
                        logger.error(f"Kafka message error on {topic}: {e}")
            finally:
                await consumer.stop()
        except Exception as e:
            logger.error(f"Kafka consumer error for {topic}: {e}")

    async def send_heartbeat(self, status: str = "active", metadata: dict = None):
        """Invia heartbeat"""
        from config import get_topics

        heartbeat = {
            "agent_id": self.agent_id,
            "agent_type": self.agent_type,
            "status": status,
            "timestamp": asyncio.get_event_loop().time(),
            "metadata": metadata or {},
        }
        await self.publish(get_topics(self.project_id)["AGENT_HEARTBEAT"], heartbeat)

    async def report_idle(self):
        """Segnala che l'agente è idle"""
        from config import get_topics

        idle_msg = {
            "agent_id": self.agent_id,
            "agent_type": self.agent_type,
            "timestamp": asyncio.get_event_loop().time(),
        }
        await self.publish(get_topics(self.project_id)["AGENT_IDLE"], idle_msg)

    async def stop(self):
        """Ferma il broker"""
        self.running = False
        logger.info(f"MessageBroker stopped for {self.agent_id}")
