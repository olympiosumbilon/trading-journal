from sqlalchemy import (
    Column,
    Integer,
    String,
    Text,
    Float,
    Boolean,
    Date,
    Time,
    DateTime,
    ForeignKey,
    func,
)
from sqlalchemy.orm import relationship
from database import Base


class Session(Base):
    __tablename__ = "sessions"
    id = Column(Integer, primary_key=True)
    name = Column(String, nullable=False)
    slug = Column(String, nullable=False, unique=True)

    trades = relationship("Trade", back_populates="session_obj")


class Instrument(Base):
    __tablename__ = "instruments"
    id = Column(Integer, primary_key=True)
    name = Column(String, nullable=False)
    slug = Column(String, nullable=False, unique=True)
    sl_buffer = Column(Float, nullable=True)
    fixed_r_target = Column(Float, nullable=True)

    trades = relationship("Trade", back_populates="instrument_obj")


class Strategy(Base):
    __tablename__ = "strategies"
    id = Column(Integer, primary_key=True)
    name = Column(String, nullable=False)
    slug = Column(String, nullable=False, unique=True)
    is_active = Column(Boolean, default=True, nullable=False)

    trades = relationship("Trade", back_populates="strategy_obj")


class ProbabilityLevel(Base):
    __tablename__ = "probability_levels"
    id = Column(Integer, primary_key=True)
    name = Column(String, nullable=False)
    slug = Column(String, nullable=False, unique=True)

    trades = relationship("Trade", back_populates="probability_level_obj")


class MTFPhase(Base):
    __tablename__ = "mtf_phases"
    id = Column(Integer, primary_key=True)
    name = Column(String, nullable=False)
    slug = Column(String, nullable=False, unique=True)

    trades = relationship("Trade", back_populates="mtf_phase_obj")


class Trade(Base):
    __tablename__ = "trades"

    id = Column(Integer, primary_key=True)

    # Entry data
    entry_date = Column(Date, nullable=True)
    entry_time = Column(Time, nullable=True)

    # Exit data & holding time
    exit_date = Column(Date, nullable=True)
    exit_time = Column(Time, nullable=True)
    holding_time_minutes = Column(Integer, nullable=True)

    # Foreign keys
    session_id = Column(Integer, ForeignKey("sessions.id"), nullable=True)
    instrument_id = Column(Integer, ForeignKey("instruments.id"), nullable=True)
    strategy_id = Column(Integer, ForeignKey("strategies.id"), nullable=True)
    probability_level_id = Column(
        Integer, ForeignKey("probability_levels.id"), nullable=True
    )
    mtf_phase_id = Column(Integer, ForeignKey("mtf_phases.id"), nullable=True)

    # News & notes
    entry_news = Column(Text, nullable=True)
    management_news = Column(Text, nullable=True)
    comments = Column(Text, nullable=True)

    # Price data
    entry_candle_size = Column(Float, nullable=True)
    mae_sl_buffer = Column(Float, nullable=True)
    mfe = Column(Float, nullable=True)

    # Screenshots
    screenshot_1 = Column(String, nullable=True)
    screenshot_2 = Column(String, nullable=True)
    screenshot_3 = Column(String, nullable=True)

    # Date derived
    day = Column(Integer, nullable=True)
    day_of_week = Column(Integer, nullable=True)
    month_number = Column(Integer, nullable=True)
    month_name = Column(String, nullable=True)
    year = Column(Integer, nullable=True)
    quarter = Column(Integer, nullable=True)

    # Execution Status: LIVE (Executed), FRONT_RUN (Unfilled), MISSED (Hesitated/Late)
    execution_status = Column(String, nullable=True, default="LIVE")
    is_sl_swept = Column(Boolean, nullable=True, default=False)

    # Execution outcome & custom Realized R (Break Even, Runner, Cut Loss, Trail)
    outcome_type = Column(String, nullable=True, default="AUTO")
    realized_r = Column(Float, nullable=True)

    # Psychology & Emotional State Tracking (Pre-Trade & Post-Trade)
    emotion_before = Column(String, nullable=True)
    emotion_after = Column(String, nullable=True)

    # Computed fields (cached from Excel; recalculated in Phase 2)
    max_r = Column(Float, nullable=True)
    fixed_r_target = Column(Float, nullable=True)
    total_r = Column(Float, nullable=True)
    is_win = Column(Boolean, nullable=True)
    win_streak = Column(Integer, nullable=True)
    is_loss = Column(Boolean, nullable=True)
    loss_streak = Column(Integer, nullable=True)
    peak_r = Column(Float, nullable=True)
    drawdown = Column(Float, nullable=True)
    max_drawdown = Column(Float, nullable=True)

    # Timestamps
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, onupdate=func.now())

    # Relationships
    session_obj = relationship("Session", back_populates="trades")
    instrument_obj = relationship("Instrument", back_populates="trades")
    strategy_obj = relationship("Strategy", back_populates="trades")
    probability_level_obj = relationship(
        "ProbabilityLevel", back_populates="trades"
    )
    mtf_phase_obj = relationship("MTFPhase", back_populates="trades")
    screenshots_list = relationship(
        "TradeScreenshot", back_populates="trade", cascade="all, delete-orphan", order_by="TradeScreenshot.order_index"
    )


class TradeScreenshot(Base):
    __tablename__ = "trade_screenshots"
    id = Column(Integer, primary_key=True)
    trade_id = Column(Integer, ForeignKey("trades.id", ondelete="CASCADE"), nullable=False)
    url = Column(String, nullable=False)
    caption = Column(String, nullable=True)
    order_index = Column(Integer, default=0)

    trade = relationship("Trade", back_populates="screenshots_list")


class CourseProgress(Base):
    __tablename__ = "course_progress"
    id = Column(Integer, primary_key=True)
    lesson_path = Column(String, nullable=False, unique=True, index=True)
    is_completed = Column(Boolean, default=False)
    last_position_seconds = Column(Float, default=0.0)
    completed_at = Column(DateTime, nullable=True)
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())


class CourseNote(Base):
    __tablename__ = "course_notes"
    id = Column(Integer, primary_key=True)
    lesson_path = Column(String, nullable=False, unique=True, index=True)
    content = Column(Text, nullable=True)
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())

