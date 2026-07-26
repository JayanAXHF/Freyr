# What our model is 

Our model is a control system for a building that already has rooftop solar and a battery. Every 15 minutes,

it decides where power should come from — solar, battery, or the grid — and whether things like AC, EV charging, or water pumps should run now or wait. The goal is simple: keep the electricity bill as low as possible without turning anything important off.

Two different “brains” are built to make these decisions, so they can be compared head-to-head:

• **MPC (the classic optimizer):** The controller recalculates optimal operating parameters and takes action in 15-minute intervals up until a day, therefore 96 intervals in a day.

• **RL / PPO (the AI agent):** a reinforcement-learning model trained in simulation to try to beat the optimizer over time.

Both run on the same simulated building, so their results can be fairly compared — that comparison is the core demo.

We use pvlib to generate an ideal clear-sky solar curve. The plan then applies synthetic degradation, i.e realistic values for processing the savings.

The primary model used is SARIMAX, ***Seasonal AutoRegressive Integrated Moving Average with eXogenous regressors***. It is a highly interpretable statistical model used for **time series forecasting** (predicting future values based on past values),


# Why it saves money

Large commercial buildings and factories pay **two types of electricity costs**:

1. **Energy cost** – how much electricity they consume (kWh).
2. **Demand charge** – based on the **highest power they draw at any one time** during the month.

A single 15-minute spike in electricity usage can increase the entire month's bill by lakhs of rupees.

Most businesses don't actively manage this because it's too complicated for humans to monitor every 15 minutes.

Our AI automates those decisions.

# Who is the target audience?

Any facility with:

- high electricity bills,
- rooftop solar,
- batteries,
- or flexible electrical loads.

Examples include:

### Manufacturing

- Automobile factories
- Textile mills
- Food processing plants
- Electronics manufacturing

These often pay huge demand charges because heavy machinery starts simultaneously.
