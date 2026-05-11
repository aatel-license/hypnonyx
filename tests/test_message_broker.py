import pytest
import asyncio
import json
from unittest.mock import AsyncMock, MagicMock, patch
from core.message_broker import MessageBroker

@pytest.fixture(autouse=True)
def clear_handlers():
    MessageBroker._in_memory_handlers.clear()
    yield
    MessageBroker._in_memory_handlers.clear()

@pytest.mark.asyncio
async def test_message_broker_init():
    broker = MessageBroker("agent_1")
    assert broker.agent_id == "agent_1"
    assert broker.running == False

@pytest.mark.asyncio
async def test_message_broker_connect_no_external(caplog):
    with patch("core.message_broker.USE_MQTT", False), \
         patch("core.message_broker.USE_KAFKA", False):
        broker = MessageBroker("agent_1")
        await broker.connect()
        assert broker.running == True
        assert "Utilizzo sistema di comunicazione in-memory" in caplog.text

@pytest.mark.asyncio
async def test_subscribe_publish_in_memory():
    broker = MessageBroker("agent_1")
    received_msgs = []
    
    async def handler(msg):
        received_msgs.append(msg)
        
    await broker.subscribe("test_topic", handler)
    await broker.publish("test_topic", {"data": "hello"})
    
    # Wait for the task to finish
    await asyncio.sleep(0.1)
    assert len(received_msgs) == 1
    assert received_msgs[0] == {"data": "hello"}

@pytest.mark.asyncio
async def test_publish_not_dict(caplog):
    broker = MessageBroker("agent_1")
    await broker.publish("topic", "not a dict")
    assert "Message must be dict" in caplog.text

@pytest.mark.asyncio
async def test_publish_handler_exception(caplog):
    import logging
    caplog.set_level(logging.ERROR)
    broker = MessageBroker("agent_1")
    
    # Use an async handler to be sure it's caught in the task
    async def failing_handler(msg):
        raise Exception("Handler failed")
        
    await broker.subscribe("test_topic", failing_handler)
    await broker.publish("test_topic", {"data": "error"})
    
    await asyncio.sleep(0.1)
    assert "Error dispatching in-memory message to handler" in caplog.text

@pytest.mark.asyncio
async def test_mqtt_connect_success(caplog):
    import logging
    caplog.set_level(logging.INFO)
    with patch("core.message_broker.USE_MQTT", True), \
         patch("core.message_broker.USE_KAFKA", False), \
         patch("aiomqtt.Client") as mock_client:
        broker = MessageBroker("agent_1")
        await broker.connect()
        assert broker.use_mqtt == True
        assert "MQTT listener avviato" in caplog.text

@pytest.mark.asyncio
async def test_mqtt_connect_fail(caplog):
    with patch("core.message_broker.USE_MQTT", True), \
         patch("core.message_broker.USE_KAFKA", False), \
         patch("aiomqtt.Client", side_effect=Exception("MQTT Fail")):
        broker = MessageBroker("agent_1")
        await broker.connect()
        assert broker.use_mqtt == False
        assert "Errore inizializzazione MQTT" in caplog.text

@pytest.mark.asyncio
async def test_kafka_connect_success(caplog):
    import logging
    caplog.set_level(logging.INFO)
    with patch("core.message_broker.USE_MQTT", False), \
         patch("core.message_broker.USE_KAFKA", True), \
         patch("aiokafka.admin.AIOKafkaAdminClient") as mock_admin, \
         patch("aiokafka.AIOKafkaProducer") as mock_producer:
        
        mock_admin_instance = mock_admin.return_value
        mock_admin_instance.start = AsyncMock()
        mock_admin_instance.list_topics = AsyncMock(return_value=["topic1"])
        mock_admin_instance.create_topics = AsyncMock()
        mock_admin_instance.close = AsyncMock()
        
        mock_producer_instance = mock_producer.return_value
        mock_producer_instance.start = AsyncMock()
        
        broker = MessageBroker("agent_1")
        await broker.connect()
        
        assert broker.use_kafka == True
        assert "Kafka Producer connesso" in caplog.text

@pytest.mark.asyncio
async def test_kafka_connect_timeout(caplog):
    with patch("core.message_broker.USE_MQTT", False), \
         patch("core.message_broker.USE_KAFKA", True), \
         patch("aiokafka.admin.AIOKafkaAdminClient") as mock_admin, \
         patch("aiokafka.AIOKafkaProducer") as mock_producer:
        
        mock_admin_instance = mock_admin.return_value
        mock_admin_instance.start = AsyncMock(side_effect=asyncio.TimeoutError)
        
        mock_producer_instance = mock_producer.return_value
        mock_producer_instance.start = AsyncMock(side_effect=asyncio.TimeoutError)
        
        broker = MessageBroker("agent_1")
        await broker.connect()
        
        assert broker.use_kafka == False
        assert "Timeout connessione Kafka" in caplog.text

@pytest.mark.asyncio
async def test_kafka_publish(caplog):
    with patch("core.message_broker.USE_KAFKA", True), \
         patch("aiokafka.AIOKafkaProducer") as mock_producer:
        
        mock_producer_instance = mock_producer.return_value
        mock_producer_instance.start = AsyncMock()
        mock_producer_instance.send_and_wait = AsyncMock()
        
        broker = MessageBroker("agent_1")
        broker._kafka_producer = mock_producer_instance
        broker.use_kafka = True
        
        await broker.publish("test_topic", {"data": "kafka"})
        mock_producer_instance.send_and_wait.assert_called()

@pytest.mark.asyncio
async def test_kafka_publish_fail(caplog):
    with patch("core.message_broker.USE_KAFKA", True), \
         patch("aiokafka.AIOKafkaProducer") as mock_producer:
        
        mock_producer_instance = mock_producer.return_value
        mock_producer_instance.send_and_wait = AsyncMock(side_effect=Exception("Kafka send fail"))
        
        broker = MessageBroker("agent_1")
        broker._kafka_producer = mock_producer_instance
        broker.use_kafka = True
        
        await broker.publish("test_topic", {"data": "kafka"})
        assert "Errore publish Kafka" in caplog.text

@pytest.mark.asyncio
async def test_heartbeat_idle():
    broker = MessageBroker("agent_1")
    broker.agent_type = "type_1"
    
    with patch.object(broker, "publish", new_callable=AsyncMock) as mock_publish:
        await broker.send_heartbeat()
        mock_publish.assert_called()
        
        await broker.report_idle()
        assert mock_publish.call_count == 2

@pytest.mark.asyncio
async def test_stop(caplog):
    import logging
    caplog.set_level(logging.INFO)
    broker = MessageBroker("agent_1")
    await broker.stop()
    assert broker.running == False
    assert "MessageBroker stopped" in caplog.text

@pytest.mark.asyncio
async def test_kafka_consume_loop_error(caplog):
    # This tests the branch where AIOKafkaConsumer fails
    with patch("aiokafka.AIOKafkaConsumer", side_effect=Exception("Consumer fail")):
        broker = MessageBroker("agent_1")
        await broker._kafka_consume_loop("test_topic")
        assert "Kafka consumer error" in caplog.text

@pytest.mark.asyncio
async def test_mqtt_loop_error(caplog):
    with patch("aiomqtt.Client", side_effect=Exception("MQTT Loop fail")):
        broker = MessageBroker("agent_1")
        broker.running = True
        await broker._mqtt_loop()
        assert "MQTT Loop failed" in caplog.text

@pytest.mark.asyncio
async def test_import_errors(caplog):
    import logging
    caplog.set_level(logging.ERROR)
    
    # Test MQTT import error
    with patch("core.message_broker.aiomqtt", None), \
         patch("core.message_broker.USE_MQTT", True):
        broker = MessageBroker("agent_1")
        await broker.connect()
        assert "USE_MQTT=true ma 'aiomqtt' non è installato" in caplog.text
        assert broker.use_mqtt == False

    # Test Kafka import error
    caplog.clear()
    with patch("core.message_broker.aiokafka", None), \
         patch("core.message_broker.USE_KAFKA", True):
        broker = MessageBroker("agent_2")
        await broker.connect()
        assert "USE_KAFKA=true ma 'aiokafka' non è installato" in caplog.text
        assert broker.use_kafka == False

@pytest.mark.asyncio
async def test_kafka_consume_loop_logic():
    broker = MessageBroker("agent_1")
    received = []
    async def handler(msg):
        received.append(msg)
    
    await broker.subscribe("test_topic", handler)
    
    mock_msg = MagicMock()
    mock_msg.value = json.dumps({"foo": "bar"}).encode()
    
    async def mock_iter(self):
        yield mock_msg
        return # Stop after one message
        
    with patch("aiokafka.AIOKafkaConsumer") as mock_consumer_cls:
        mock_consumer = mock_consumer_cls.return_value
        mock_consumer.start = AsyncMock()
        mock_consumer.stop = AsyncMock()
        mock_consumer.__aiter__ = mock_iter
        
        # We need to limit the loop or it will run forever
        # Actually, the mock_iter yields once and then stops
        await broker._kafka_consume_loop("test_topic")
        
        assert len(received) == 1
        assert received[0] == {"foo": "bar"}

@pytest.mark.asyncio
async def test_mqtt_loop_logic():
    broker = MessageBroker("agent_1")
    received = []
    async def handler(msg):
        received.append(msg)
    
    await broker.subscribe("test_topic", handler)
    
    mock_msg = MagicMock()
    mock_msg.topic = "test_topic"
    mock_msg.payload = json.dumps({"hello": "world"}).encode()
    
    async def mock_iter(self):
        yield mock_msg
        return
        
    with patch("aiomqtt.Client") as mock_client_cls:
        mock_client = mock_client_cls.return_value
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock()
        mock_client.subscribe = AsyncMock()
        mock_client.messages = MagicMock()
        mock_client.messages.__aiter__ = mock_iter
        
        await broker._mqtt_loop()
        
        assert len(received) == 1
        assert received[0] == {"hello": "world"}
