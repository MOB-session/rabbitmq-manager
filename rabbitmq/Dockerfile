FROM rabbitmq:4.1-management

# Copy enabled plugins (management + shovel)
COPY enabled_plugins /etc/rabbitmq/enabled_plugins

# Copy custom configuration
COPY rabbitmq.conf /etc/rabbitmq/rabbitmq.conf

EXPOSE 5672 15672
