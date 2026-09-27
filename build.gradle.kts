plugins {
    // AGP 8.7.x uses the explicit Kotlin Android plugin below. AGP 9.x
    // enables an integrated Kotlin plugin and conflicts with that marker.
    id("com.android.application") version "8.7.3" apply false
}
