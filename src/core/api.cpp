#include "api.hpp"
#include "core/context.hpp"
#include "core/common.hpp"

// Platform information
#include <stdexcept>
#include <sys/sysinfo.h>
#include <sys/utsname.h>

namespace ietf::sys {
namespace API {
    /**
     * @brief Get system hostname.
     *
     * @return Hostname.
     */
    std::string System::getHostname()
    {
        char hostname[ietf::sys::HOSTNAME_MAX_LEN + 1] = { 0 };

        if (gethostname(hostname, sizeof(hostname)) < 0) {
            throw std::runtime_error("Failed to get hostname.");
        }

        return hostname;
    }

    /**
     * @brief Get platform information.
     *
     * @return Platform information.
     */
    PlatformInfo SystemState::getPlatformInfo()
    {
        struct utsname uname_data = { 0 };

        if (uname(&uname_data) < 0) {
            throw std::runtime_error("Failed to get platform information.");
        }

        return {
            .OsName = uname_data.sysname,
            .OsRelease = uname_data.release,
            .OsVersion = uname_data.version,
            .Machine = uname_data.machine,
        };
    }

    /**
     * @brief Get clock information.
     *
     * @return Clock information.
     */
    ClockInfo SystemState::getClockInfo()
    {
        time_t now = 0;
        struct tm* ts = { 0 };
        struct sysinfo s_info = { 0 };
        time_t uptime_seconds = 0;

        char current_datetime[256];
        char boot_datetime[256];

        now = time(NULL);

        ts = localtime(&now);
        if (ts == NULL) {
            throw std::runtime_error("Failed to get current datetime.");
        }

        strftime(current_datetime, sizeof(current_datetime), "%FT%TZ", ts);

        if (sysinfo(&s_info) != 0) {
            throw std::runtime_error("Failed to get system uptime.");
        }

        uptime_seconds = s_info.uptime;

        time_t diff = now - uptime_seconds;

        ts = localtime(&diff);
        if (ts == NULL) {
            throw std::runtime_error("Failed to get boot datetime.");
        }

        strftime(boot_datetime, sizeof(boot_datetime), "%FT%TZ", ts);

        return {
            .BootDatetime = boot_datetime,
            .CurrentDatetime = current_datetime,
        };
    }
}
}